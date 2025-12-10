#include "llvm/CodeGen/IRAnalysisPass.h"
#include "llvm/CodeGen/MachineFunction.h"
#include "llvm/CodeGen/MachineFunctionPass.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/Module.h"
#include "llvm/InitializePasses.h"
#include "llvm/PassRegistry.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Transforms/Yk/ControlPoint.h"
#include "llvm/Transforms/Yk/ModuleClone.h"
#include "llvm/YkIR/YkIRWriter.h"
#include <algorithm>
#include <cstddef>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using namespace llvm;

namespace {
const bool PrintMIR = false;
const bool CountAddressTakenFunctions = true;
const char *CSV_OUTPUT_PATH = "/home/pd/ir_analysis_basicblocks.csv";
const char *CSV_FUNCTION_TRACING_PATH = "/home/pd/function_tracing_status.csv";
const char *YK_TRACE_FUNCTION = "__yk_trace_basicblock";

// Analysis mode configuration
enum class AnalysisMode {
  TRACING_BLOCKS_ONLY,     // Analyze only blocks with tracing calls
  NON_TRACING_BLOCKS_ONLY, // Analyze only blocks without tracing calls
  BOTH                     // Analyze both types (current behavior)
};

// Set the desired analysis mode here
const AnalysisMode ANALYSIS_MODE = AnalysisMode::BOTH;

// Control whether to print per-function statistics
const bool PRINT_FUNCTION_STATS = false;

// Control whether to print address-taken functions
const bool PRINT_ADDRESS_TAKEN_FUNCTIONS = false;

// Control whether to skip debug, pseudo, and meta instructions in MIR counting
const bool SKIP_DEBUG_PSEUDO_INSTRUCTIONS = true;

// Control whether to print functions by non-tracing reason
const bool PRINT_FUNCTIONS_BY_REASON = false;

// Enum for reasons why a function is not traced
enum class NonTracingReason {
  OPTIMISED_CLONE,          // __yk_opt_ clone (has YK_SWT_OPT_MD metadata)
  OUTLINED_NO_CONTROL_POINT, // Has YK_OUTLINE_FNATTR but no control point
  OUTLINED_WITH_CONTROL_POINT, // Has YK_OUTLINE_FNATTR with control point (traced)
  TRACED                     // Function is traced (not a non-tracing function)
};

struct FunctionStats {
  std::string functionName;
  size_t numIRBasicBlocks;
  size_t numIRInstructions;
  size_t numMIRBasicBlocks;
  size_t numMIRInstructions;
};

struct BasicBlockInfo {
  std::string functionName;
  std::string basicBlockId;
  std::vector<std::string> instructions;
};

// Helper function to determine why a function is not traced (or if it is traced)
// This follows the same logic as BasicBlockTracer.cpp
static NonTracingReason getTracingStatus(const Function &F) {
  // Check if it's an optimised clone (has YK_SWT_OPT_MD metadata)
  if (F.getMetadata(YK_SWT_OPT_MD)) {
    return NonTracingReason::OPTIMISED_CLONE;
  }
  
  // Check if it's outlined without a control point
  if (containsControlPoint(const_cast<Function&>(F))) {
    return NonTracingReason::OUTLINED_WITH_CONTROL_POINT;
  }else if (F.hasFnAttribute(YK_OUTLINE_FNATTR)) {
    return NonTracingReason::OUTLINED_NO_CONTROL_POINT;
  }
  
  // Otherwise, it's traced
  return NonTracingReason::TRACED;
}

// Helper function to get a human-readable description of the non-tracing reason
static const char* getReasonDescription(NonTracingReason reason) {
  switch (reason) {
    case NonTracingReason::OPTIMISED_CLONE:
      return "Optimised clone (__yk_opt_*)";
    case NonTracingReason::OUTLINED_NO_CONTROL_POINT:
      return "Outlined function without control point";
    case NonTracingReason::TRACED:
      return "Traced";
  }
  return "Unknown";
}

// Helper function to check if an IR basic block contains tracing calls
static bool containsTracingCall(const BasicBlock &BB) {
  for (const Instruction &I : BB) {
    if (const CallInst *CI = dyn_cast<CallInst>(&I)) {
      if (Function *Callee = CI->getCalledFunction()) {
        if (Callee->getName() == YK_TRACE_FUNCTION) {
          return true;
        }
      }
    }
  }
  return false;
}

// Helper function to determine if a block should be included based on analysis mode
static bool shouldIncludeBlock(bool hasTracingCall) {
  switch (ANALYSIS_MODE) {
    case AnalysisMode::TRACING_BLOCKS_ONLY:
      return hasTracingCall;
    case AnalysisMode::NON_TRACING_BLOCKS_ONLY:
      return !hasTracingCall;
    case AnalysisMode::BOTH:
      return true;
  }
  return false;
}

// Helper function to determine if a MIR instruction should be counted
static bool shouldCountInstruction(const MachineInstr &MI) {
  if (!SKIP_DEBUG_PSEUDO_INSTRUCTIONS) {
    return true;
  }

  // Skip debug, pseudo, meta, position, probe, and frame setup/destroy instructions
  return !MI.isDebugInstr() && !MI.isPseudo() && !MI.isMetaInstruction() &&
         !MI.isPosition() && !MI.isPseudoProbe() &&
         !MI.getFlag(MachineInstr::FrameSetup) &&
         !MI.getFlag(MachineInstr::FrameDestroy);
}

static void collectInstructionType(const MachineInstr &MI, std::set<std::string> &uniqueInstructionTypes, 
                                   std::set<std::string> &filteredOutInstructions, const TargetInstrInfo *TII) {
  if (shouldCountInstruction(MI)) {
    // Get instruction name/opcode using TargetInstrInfo
    std::string instrName = TII->getName(MI.getOpcode()).str();
    uniqueInstructionTypes.insert(instrName);
  } else {
    // Collect debug/pseudo instructions that are filtered out
    std::string instrName = TII->getName(MI.getOpcode()).str();

    // Get full instruction text
    std::string instrStr;
    raw_string_ostream rso(instrStr);
    MI.print(rso);
    rso.flush();

    // Remove newlines and clean up the string
    instrStr.erase(std::remove(instrStr.begin(), instrStr.end(), '\n'), instrStr.end());
    instrStr.erase(std::remove(instrStr.begin(), instrStr.end(), '\r'), instrStr.end());
    
    // Truncate instruction string to first 20 characters
    if (instrStr.length() > 20) {
      instrStr = instrStr.substr(0, 20) + "...";
    }
    
    // Create entry with type and truncated instruction
    std::string entry = instrName + ": " + instrStr;
    filteredOutInstructions.insert(entry);
  }
}

// Helper function to check if a MIR basic block contains tracing calls
static bool containsTracingCall(const MachineBasicBlock &MBB) {
  for (const MachineInstr &MI : MBB) {
    if (MI.isCall()) {
      // Check if this is a call to the tracing function
      for (const MachineOperand &MO : MI.operands()) {
        if (MO.isGlobal()) {
          const GlobalValue *GV = MO.getGlobal();
          if (GV->getName() == YK_TRACE_FUNCTION) {
            return true;
          }
        }
      }
    }
  }
  return false;
}

// Helper function to escape CSV fields
static std::string escapeCSVField(const std::string &field) {
  bool needsQuotes = false;
  std::string result;

  // Check if the field contains special characters
  if (field.find(',') != std::string::npos ||
      field.find('"') != std::string::npos ||
      field.find('\n') != std::string::npos ||
      field.find('\r') != std::string::npos) {
    needsQuotes = true;
  }

  if (needsQuotes) {
    result = "\"";
    for (char c : field) {
      if (c == '"') {
        result += "\"\""; // Escape quotes by doubling them
      } else {
        result += c;
      }
    }
    result += "\"";
  } else {
    result = field;
  }

  return result;
}

} // anonymous namespace

namespace llvm {

class IRAnalysisPass : public MachineFunctionPass {
public:
  static char ID;
  IRAnalysisPass();

  bool runOnMachineFunction(MachineFunction &MF) override;

  ~IRAnalysisPass() override;

private:
  // Map from module name to (IRBBs, IRInsts, MIRBBs, MIRInsts)
  struct ModuleStats {
    size_t numIRBasicBlocks = 0;
    size_t numIRInstructions = 0;
    size_t numMIRBasicBlocks = 0;
    size_t numMIRInstructions = 0;
  };
  std::map<std::string, ModuleStats> moduleStats;
  // Vector to store per-function statistics
  std::vector<FunctionStats> functionStats;
  // Track address-taken functions
  std::set<std::string> addressTakenFunctions;
  // Track optimised functions (cloned with YK_SWT_OPT_MD metadata)
  std::set<std::string> optFunctions;
  // Track unoptimised functions (with OptimizeNone attribute)
  std::set<std::string> unoptFunctions;
  // Track outlined functions (with yk_outline attribute)
  std::set<std::string> outlinedFunctions;
  // Vector to store basic block information with instructions
  std::vector<BasicBlockInfo> basicBlockInfoList;
  // Track if CSV header has been written
  bool csvHeaderWritten;
  // Set to store unique instruction types and names that pass filtering criteria
  std::set<std::string> uniqueInstructionTypes;
  // Set to store debug/pseudo instructions that are filtered out
  std::set<std::string> filteredOutInstructions;
  // Track functions by their tracing status
  std::map<NonTracingReason, std::set<std::string>> functionsByTracingStatus;
  size_t totalFunctions;
};

} // namespace llvm

IRAnalysisPass::IRAnalysisPass() : MachineFunctionPass(ID), csvHeaderWritten(false), totalFunctions(0) {
  initializeIRAnalysisPassPass(*PassRegistry::getPassRegistry());
}

bool IRAnalysisPass::runOnMachineFunction(MachineFunction &MF) {
  // Get the module name and function
  const Module *M = MF.getFunction().getParent();
  std::string moduleName = M->getName().str();
  const Function &F = MF.getFunction();
  std::string functionName = MF.getName().str();

  // Track total functions and their tracing status
  totalFunctions++;
  NonTracingReason tracingStatus = getTracingStatus(F);
  functionsByTracingStatus[tracingStatus].insert(functionName);

  // Track address-taken functions
  if (CountAddressTakenFunctions && F.hasAddressTaken()) {
    // Track address-taken functions
    addressTakenFunctions.insert(functionName);
  } else if (F.getMetadata(YK_SWT_OPT_MD)) {
    // Track optimised functions (those with YK_SWT_OPT_MD metadata)
    optFunctions.insert(functionName);
  } else if (F.hasFnAttribute(YK_OUTLINE_FNATTR)) {
    // Track outlined functions (those with yk_outline attribute)
    outlinedFunctions.insert(functionName);
  } else {
    // Track unoptimised functions (those with OptimizeNone attribute)
    unoptFunctions.insert(functionName);
  }

  // Count AOT IR basic blocks and instructions (excluding debug info)
  size_t numIRBBs = 0;
  size_t numIRInsts = 0;
  for (const BasicBlock &BB : F) {
    numIRBBs++;
    for (const Instruction &I : BB) {
      // Exclude debug intrinsics from the count
      if (!isa<DbgInfoIntrinsic>(&I)) {
        numIRInsts++;
      }
    }
  }

  // Count MIR basic blocks and instructions (excluding debug info)
  // and collect detailed basic block information
  size_t numMIRBBs = 0;
  size_t numMIRInsts = 0;
  for (const MachineBasicBlock &MBB : MF) {
    numMIRBBs++;

    // Create basic block info
    BasicBlockInfo bbInfo;
    bbInfo.functionName = functionName;
    bbInfo.basicBlockId = "BB#" + std::to_string(MBB.getNumber());

    for (const MachineInstr &MI : MBB) {
      // Exclude debug instructions from the count
      if (!MI.isDebugInstr()) {
        numMIRInsts++;

        // Convert instruction to string
        std::string instrStr;
        raw_string_ostream rso(instrStr);
        MI.print(rso);
        rso.flush();

        // Remove newlines and clean up the string
        instrStr.erase(std::remove(instrStr.begin(), instrStr.end(), '\n'),
                       instrStr.end());
        instrStr.erase(std::remove(instrStr.begin(), instrStr.end(), '\r'),
                       instrStr.end());

        bbInfo.instructions.push_back(instrStr);
      }
    }

    // Only add basic blocks that have instructions
    if (!bbInfo.instructions.empty()) {
      basicBlockInfoList.push_back(bbInfo);
    }
  }

  // Store per-function statistics
  FunctionStats funcStats;
  funcStats.functionName = functionName;
  funcStats.numIRBasicBlocks = numIRBBs;
  funcStats.numIRInstructions = numIRInsts;
  funcStats.numMIRBasicBlocks = numMIRBBs;
  funcStats.numMIRInstructions = numMIRInsts;
  functionStats.push_back(funcStats);

  // Aggregate module statistics
  ModuleStats &stats = moduleStats[moduleName];
  stats.numIRBasicBlocks += numIRBBs;
  stats.numIRInstructions += numIRInsts;
  stats.numMIRBasicBlocks += numMIRBBs;
  stats.numMIRInstructions += numMIRInsts;

  // Write basic block information to CSV file incrementally
  std::ofstream csvFile;

  // Check if file exists to determine if we need to write header
  std::ifstream checkFile(CSV_OUTPUT_PATH);
  bool fileExists = checkFile.good();
  checkFile.close();

  if (!fileExists && !csvHeaderWritten) {
    // First time: create file and write header
    csvFile.open(CSV_OUTPUT_PATH, std::ios::out);
    if (csvFile.is_open()) {
      csvFile << "function_name,basicblock_id,number_of_instructions,"
                 "instructions\n";
      csvHeaderWritten = true;
      errs() << "Created CSV file: " << CSV_OUTPUT_PATH << "\n";
    } else {
      errs() << "Error: Could not create CSV file: " << CSV_OUTPUT_PATH << "\n";
      return false;
    }
  } else {
    // Append mode - file exists or header already written
    csvFile.open(CSV_OUTPUT_PATH, std::ios::app);
    if (!csvFile.is_open()) {
      errs() << "Error: Could not open CSV file for appending: "
             << CSV_OUTPUT_PATH << "\n";
      return false;
    }
    csvHeaderWritten = true;
  }

  if (csvFile.is_open()) {
    // Write basic block information for this function
    for (const auto &bbInfo : basicBlockInfoList) {
      // Only write if it belongs to the current function
      if (bbInfo.functionName == functionName) {
        std::string escapedFunctionName = escapeCSVField(bbInfo.functionName);
        std::string escapedBasicBlockId = escapeCSVField(bbInfo.basicBlockId);

        // Join instructions with semicolon separator
        std::string instructionsStr;
        for (size_t i = 0; i < bbInfo.instructions.size(); ++i) {
          if (i > 0) {
            instructionsStr += "; ";
          }
          instructionsStr += bbInfo.instructions[i];
        }
        std::string escapedInstructions = escapeCSVField(instructionsStr);

        csvFile << escapedFunctionName << "," << escapedBasicBlockId << ","
                << bbInfo.instructions.size() << "," << escapedInstructions
                << "\n";
      }
    }
    csvFile.close();
  }

  // Write function stats to CSV file
  std::ofstream funcStatsCsvFile;

  // Check if file exists to determine if we need to write header
  std::ifstream checkFuncStatsFile(FUNC_STATS_CSV_PATH);
  bool funcStatsFileExists = checkFuncStatsFile.good();
  checkFuncStatsFile.close();

  if (!funcStatsFileExists && !funcStatsCsvHeaderWritten) {
    // First time: create file and write header
    funcStatsCsvFile.open(FUNC_STATS_CSV_PATH, std::ios::out);
    if (funcStatsCsvFile.is_open()) {
      funcStatsCsvFile << "function_name,function_index,is_optimised,is_"
                          "unoptimised,is_address_taken,is_outlined\n";
      funcStatsCsvHeaderWritten = true;
      errs() << "Created function stats CSV file: " << FUNC_STATS_CSV_PATH
             << "\n";
    } else {
      errs() << "Error: Could not create function stats CSV file: "
             << FUNC_STATS_CSV_PATH << "\n";
      return false;
    }
  } else {
    // Append mode - file exists or header already written
    funcStatsCsvFile.open(FUNC_STATS_CSV_PATH, std::ios::app);
    if (!funcStatsCsvFile.is_open()) {
      errs() << "Error: Could not open function stats CSV file for appending: "
             << FUNC_STATS_CSV_PATH << "\n";
      return false;
    }
    funcStatsCsvHeaderWritten = true;
  }

  if (funcStatsCsvFile.is_open()) {
    // Determine boolean flags for this function
    bool isOptimised = optFunctions.count(functionName) > 0;
    bool isUnoptimised = unoptFunctions.count(functionName) > 0;
    bool isAddressTaken = addressTakenFunctions.count(functionName) > 0;
    bool isOutlined = outlinedFunctions.count(functionName) > 0;

    std::string escapedFunctionName = escapeCSVField(functionName);

    funcStatsCsvFile << escapedFunctionName << "," << functionIndex << ","
                     << (isOptimised ? "true" : "false") << ","
                     << (isUnoptimised ? "true" : "false") << ","
                     << (isAddressTaken ? "true" : "false") << ","
                     << (isOutlined ? "true" : "false") << "\n";
    funcStatsCsvFile.close();
  }

  // Increment function index for the next function
  functionIndex++;

  return false;
}

IRAnalysisPass::~IRAnalysisPass() {
  errs() << "=== IR Analysis Pass Statistics ===\n\n";

  for (const auto &entry : moduleStats) {
    const std::string &moduleName = entry.first;
    const ModuleStats &stats = entry.second;

    double avgIRInstsPerBlock =
        stats.numIRBasicBlocks > 0
            ? static_cast<double>(stats.numIRInstructions) /
                  stats.numIRBasicBlocks
            : 0.0;

    double avgMIRInstsPerBlock =
        stats.numMIRBasicBlocks > 0
            ? static_cast<double>(stats.numMIRInstructions) /
                  stats.numMIRBasicBlocks
            : 0.0;

    errs() << "Module: " << moduleName << "\n"
           << "  AOT IR Statistics:\n"
           << "    Total Basic Blocks: " << stats.numIRBasicBlocks << "\n"
           << "    Total Instructions: " << stats.numIRInstructions << "\n"
           << "    Average Instructions per Block: " << avgIRInstsPerBlock
           << "\n"
           << "  MIR Statistics:\n"
           << "    Total Basic Blocks: " << stats.numMIRBasicBlocks << "\n"
           << "    Total Instructions: " << stats.numMIRInstructions << "\n"
           << "    Average Instructions per Block: " << avgMIRInstsPerBlock
           << "\n\n";
  }
  errs() << "===========================\n";

  // Print per-function statistics if enabled
  if (PRINT_FUNCTION_STATS && !functionStats.empty()) {
    errs() << "\n=== Per-Function Statistics ===\n";
    for (const auto &funcStat : functionStats) {
      errs() << "Function: " << funcStat.functionName << "\n";
      if (ANALYSIS_MODE == AnalysisMode::TRACING_BLOCKS_ONLY) {
        errs() << "  IR Tracing Blocks: " << funcStat.numIRBasicBlocks 
               << ", Tracing Block Instructions: " << funcStat.numIRInstructions << "\n";
        errs() << "  MIR Tracing Blocks: " << funcStat.numMIRBasicBlocks 
               << ", Tracing Block Instructions: " << funcStat.numMIRInstructions << "\n";
      } else if (ANALYSIS_MODE == AnalysisMode::NON_TRACING_BLOCKS_ONLY) {
        errs() << "  IR Non-Tracing Blocks: " << funcStat.numIRBasicBlocks 
               << ", Non-Tracing Block Instructions: " << funcStat.numIRInstructions << "\n";
        errs() << "  MIR Non-Tracing Blocks: " << funcStat.numMIRBasicBlocks 
               << ", Non-Tracing Block Instructions: " << funcStat.numMIRInstructions << "\n";
      } else { // BOTH
        errs() << "  IR Total: " << funcStat.numIRBasicBlocks << " blocks, " 
               << funcStat.numIRInstructions << " instructions\n";
        errs() << "  IR Tracing: " << funcStat.numIRTracingBlocks << " blocks, " 
               << funcStat.numIRTracingInstructions << " tracing block instructions\n";
        errs() << "  IR Non-Tracing: " << funcStat.numIRNonTracingBlocks << " blocks, " 
               << funcStat.numIRNonTracingInstructions << " non-tracing block instructions\n";
        errs() << "  MIR Total: " << funcStat.numMIRBasicBlocks << " blocks, " 
               << funcStat.numMIRInstructions << " instructions\n";
        errs() << "  MIR Tracing: " << funcStat.numMIRTracingBlocks << " blocks, " 
               << funcStat.numMIRTracingInstructions << " tracing block instructions\n";
        errs() << "  MIR Non-Tracing: " << funcStat.numMIRNonTracingBlocks << " blocks, " 
               << funcStat.numMIRNonTracingInstructions << " non-tracing block instructions\n";
      }
      errs() << "\n";
    }
    errs() << "==============================\n";
  }

  // Print address-taken functions if enabled
  if (CountAddressTakenFunctions && PRINT_ADDRESS_TAKEN_FUNCTIONS && !addressTakenFunctions.empty()) {
    errs() << "\n=== Address-Taken Functions ===\n";
    errs() << "Total: " << addressTakenFunctions.size() << "\n";
    for (const auto &funcName : addressTakenFunctions) {
      errs() << "  " << funcName << "\n";
    }
    errs() << "==============================\n";
  }

  // Write function tracing status to CSV file
  std::ofstream csvFunctionFile(CSV_FUNCTION_TRACING_PATH);
  if (csvFunctionFile.is_open()) {
    // Write CSV header
    csvFunctionFile << "function_name,has_tracing_calls,reason_for_no_tracing\n";

    // Write all functions with their tracing status
    for (const auto &entry : functionsByTracingStatus) {
      NonTracingReason reason = entry.first;
      const std::set<std::string> &functions = entry.second;

      for (const auto &funcName : functions) {
        std::string escapedFunctionName = escapeCSVField(funcName);
        bool hasTracingCalls = (reason == NonTracingReason::TRACED);
        std::string reasonStr = hasTracingCalls ? "" : getReasonDescription(reason);
        std::string escapedReason = escapeCSVField(reasonStr);

        csvFunctionFile << escapedFunctionName << ","
                       << (hasTracingCalls ? "true" : "false") << ","
                       << escapedReason << "\n";
      }
    }

    csvFunctionFile.close();
    errs() << "\nFunction tracing status written to: " << CSV_FUNCTION_TRACING_PATH << "\n";
  } else {
    errs() << "Error: Could not create function tracing CSV file: " << CSV_FUNCTION_TRACING_PATH << "\n";
  }

  // Print summary statistics
  errs() << "\n=== Function Tracing Status Summary ===\n";
  errs() << "Total functions processed: " << totalFunctions << "\n";

  size_t tracedFunctions = functionsByTracingStatus[NonTracingReason::TRACED].size();
  size_t optimisedClones = functionsByTracingStatus[NonTracingReason::OPTIMISED_CLONE].size();
  size_t outlinedNoCP = functionsByTracingStatus[NonTracingReason::OUTLINED_NO_CONTROL_POINT].size();
  size_t nonTracedTotal = optimisedClones + outlinedNoCP;

  errs() << "Traced functions: " << tracedFunctions
         << " (" << format("%.1f%%", (tracedFunctions * 100.0) / totalFunctions) << ")\n";
  errs() << "Non-traced functions: " << nonTracedTotal
         << " (" << format("%.1f%%", (nonTracedTotal * 100.0) / totalFunctions) << ")\n";
  errs() << "  - Optimised clones (__yk_opt_*): " << optimisedClones
         << " (" << format("%.1f%%", (optimisedClones * 100.0) / totalFunctions) << ")\n";
  errs() << "  - Outlined without control point: " << outlinedNoCP
         << " (" << format("%.1f%%", (outlinedNoCP * 100.0) / totalFunctions) << ")\n";

  if (nonTracedTotal > 0 && tracedFunctions > 0) {
    double ratio = static_cast<double>(nonTracedTotal) / tracedFunctions;
    errs() << "Ratio (non-traced:traced): " << format("%.2f", ratio) << ":1\n";
  }
  errs() << "=======================================\n";

  // Print unique instruction types that passed filtering criteria
  if (!uniqueInstructionTypes.empty()) {
    errs() << "\n=== Unique MIR Instruction Types (Counted) ===\n";
    errs() << "Total unique instruction types: " << uniqueInstructionTypes.size() << "\n";
    for (const auto &instrType : uniqueInstructionTypes) {
      errs() << "  " << instrType << "\n";
    }
    errs() << "==============================================\n";
  }

  // Print debug/pseudo instructions that were filtered out
  if (!filteredOutInstructions.empty()) {
    errs() << "\n=== Debug/Pseudo Instructions (Filtered Out) ===\n";
    errs() << "Total unique filtered instructions: " << filteredOutInstructions.size() << "\n";
    for (const auto &instrEntry : filteredOutInstructions) {
      errs() << "  " << instrEntry << "\n";
    }
    errs() << "================================================\n";
  }

  // CSV file was written incrementally during pass execution
  if (csvHeaderWritten) {
    errs() << "\nBasic block information written to: " << CSV_OUTPUT_PATH
           << "\n";
    errs() << "Total basic blocks processed: " << basicBlockInfoList.size()
           << "\n";
  }

  if (funcStatsCsvHeaderWritten) {
    errs() << "Function statistics written to: " << FUNC_STATS_CSV_PATH << "\n";
  }
}

char IRAnalysisPass::ID = 0;
INITIALIZE_PASS(IRAnalysisPass, "ir-analysis-pass", "IR Analysis Pass", false,
                false)

namespace llvm {
MachineFunctionPass *createIRAnalysisPass() { return new IRAnalysisPass(); }
} // namespace llvm
