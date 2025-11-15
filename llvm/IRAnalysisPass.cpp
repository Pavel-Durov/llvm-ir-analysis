#include "llvm/CodeGen/IRAnalysisPass.h"
#include "llvm/CodeGen/MachineFunction.h"
#include "llvm/CodeGen/MachineFunctionPass.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/Module.h"
#include "llvm/InitializePasses.h"
#include "llvm/PassRegistry.h"
#include "llvm/Support/raw_ostream.h"
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

struct FunctionStats {
  std::string functionName;
  size_t numIRBasicBlocks;
  size_t numIRInstructions;
  size_t numMIRBasicBlocks;
  size_t numMIRInstructions;
  // Separate stats for tracing vs non-tracing blocks
  size_t numIRTracingBlocks;
  size_t numIRTracingInstructions;
  size_t numIRNonTracingBlocks;
  size_t numIRNonTracingInstructions;
  size_t numMIRTracingBlocks;
  size_t numMIRTracingInstructions;
  size_t numMIRNonTracingBlocks;
  size_t numMIRNonTracingInstructions;
};

struct BasicBlockInfo {
  std::string functionName;
  std::string basicBlockId;
  std::vector<std::string> instructions;
  bool hasTracingCall;
};

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
    // Separate stats for tracing vs non-tracing blocks
    size_t numIRTracingBlocks = 0;
    size_t numIRTracingInstructions = 0;
    size_t numIRNonTracingBlocks = 0;
    size_t numIRNonTracingInstructions = 0;
    size_t numMIRTracingBlocks = 0;
    size_t numMIRTracingInstructions = 0;
    size_t numMIRNonTracingBlocks = 0;
    size_t numMIRNonTracingInstructions = 0;
  };
  std::map<std::string, ModuleStats> moduleStats;
  // Vector to store per-function statistics
  std::vector<FunctionStats> functionStats;
  // Track address-taken functions
  std::set<std::string> addressTakenFunctions;
  // Vector to store basic block information with instructions
  std::vector<BasicBlockInfo> basicBlockInfoList;
  // Track if CSV header has been written
  bool csvHeaderWritten;
};

} // namespace llvm

IRAnalysisPass::IRAnalysisPass() : MachineFunctionPass(ID), csvHeaderWritten(false) {
  initializeIRAnalysisPassPass(*PassRegistry::getPassRegistry());
}

bool IRAnalysisPass::runOnMachineFunction(MachineFunction &MF) {
  // Get the module name and function
  const Module *M = MF.getFunction().getParent();
  std::string moduleName = M->getName().str();
  const Function &F = MF.getFunction();
  std::string functionName = MF.getName().str();

  // Track address-taken functions
  if (CountAddressTakenFunctions && F.hasAddressTaken()) {
    addressTakenFunctions.insert(functionName);
  }

  // Count AOT IR basic blocks and instructions (excluding debug info)
  // Count based on selected analysis mode
  size_t numIRBBs = 0;
  size_t numIRInsts = 0;
  size_t numIRTracingBBs = 0;
  size_t numIRTracingInsts = 0;
  size_t numIRNonTracingBBs = 0;
  size_t numIRNonTracingInsts = 0;

  for (const BasicBlock &BB : F) {
    bool hasTracing = containsTracingCall(BB);

    // Only process blocks that match our analysis mode
    if (shouldIncludeBlock(hasTracing)) {
      numIRBBs++;

      size_t blockInsts = 0;
      for (const Instruction &I : BB) {
        // Exclude debug intrinsics from the count
        if (!isa<DbgInfoIntrinsic>(&I)) {
          blockInsts++;
          numIRInsts++;
        }
      }
    }

    // Always track separate counts for statistics display
    size_t blockInsts = 0;
    for (const Instruction &I : BB) {
      if (!isa<DbgInfoIntrinsic>(&I)) {
        blockInsts++;
      }
    }

    if (hasTracing) {
      numIRTracingBBs++;
      numIRTracingInsts += blockInsts;
    } else {
      numIRNonTracingBBs++;
      numIRNonTracingInsts += blockInsts;
    }
  }

  // Count MIR basic blocks and instructions (excluding debug info)
  // and collect detailed basic block information
  // Count based on selected analysis mode
  size_t numMIRBBs = 0;
  size_t numMIRInsts = 0;
  size_t numMIRTracingBBs = 0;
  size_t numMIRTracingInsts = 0;
  size_t numMIRNonTracingBBs = 0;
  size_t numMIRNonTracingInsts = 0;

  for (const MachineBasicBlock &MBB : MF) {
    bool hasTracing = containsTracingCall(MBB);

    // Only process blocks that match our analysis mode
    if (shouldIncludeBlock(hasTracing)) {
      numMIRBBs++;

      // Create basic block info
      BasicBlockInfo bbInfo;
      bbInfo.functionName = functionName;
      bbInfo.basicBlockId = "BB#" + std::to_string(MBB.getNumber());
      bbInfo.hasTracingCall = hasTracing;

      size_t blockInsts = 0;
      for (const MachineInstr &MI : MBB) {
        // Use helper function to determine if instruction should be counted
        if (shouldCountInstruction(MI)) {
          blockInsts++;
          numMIRInsts++;
          
          // Convert instruction to string
          std::string instrStr;
          raw_string_ostream rso(instrStr);
          MI.print(rso);
          rso.flush();

          // Remove newlines and clean up the string
          instrStr.erase(std::remove(instrStr.begin(), instrStr.end(), '\n'), instrStr.end());
          instrStr.erase(std::remove(instrStr.begin(), instrStr.end(), '\r'), instrStr.end());
          
          bbInfo.instructions.push_back(instrStr);
        }
      }

      // Add basic blocks that have instructions and match analysis mode
      if (!bbInfo.instructions.empty()) {
        basicBlockInfoList.push_back(bbInfo);
      }
    }

    // Always track separate counts for statistics display
    size_t blockInsts = 0;
    for (const MachineInstr &MI : MBB) {
      if (shouldCountInstruction(MI)) {
        blockInsts++;
      }
    }

    if (hasTracing) {
      numMIRTracingBBs++;
      numMIRTracingInsts += blockInsts;
    } else {
      numMIRNonTracingBBs++;
      numMIRNonTracingInsts += blockInsts;
    }
  }

  // Store per-function statistics
  FunctionStats funcStats;
  funcStats.functionName = functionName;
  funcStats.numIRBasicBlocks = numIRBBs;
  funcStats.numIRInstructions = numIRInsts;
  funcStats.numMIRBasicBlocks = numMIRBBs;
  funcStats.numMIRInstructions = numMIRInsts;
  funcStats.numIRTracingBlocks = numIRTracingBBs;
  funcStats.numIRTracingInstructions = numIRTracingInsts;
  funcStats.numIRNonTracingBlocks = numIRNonTracingBBs;
  funcStats.numIRNonTracingInstructions = numIRNonTracingInsts;
  funcStats.numMIRTracingBlocks = numMIRTracingBBs;
  funcStats.numMIRTracingInstructions = numMIRTracingInsts;
  funcStats.numMIRNonTracingBlocks = numMIRNonTracingBBs;
  funcStats.numMIRNonTracingInstructions = numMIRNonTracingInsts;
  functionStats.push_back(funcStats);

  // Aggregate module statistics
  ModuleStats &stats = moduleStats[moduleName];
  stats.numIRBasicBlocks += numIRBBs;
  stats.numIRInstructions += numIRInsts;
  stats.numMIRBasicBlocks += numMIRBBs;
  stats.numMIRInstructions += numMIRInsts;
  stats.numIRTracingBlocks += numIRTracingBBs;
  stats.numIRTracingInstructions += numIRTracingInsts;
  stats.numIRNonTracingBlocks += numIRNonTracingBBs;
  stats.numIRNonTracingInstructions += numIRNonTracingInsts;
  stats.numMIRTracingBlocks += numMIRTracingBBs;
  stats.numMIRTracingInstructions += numMIRTracingInsts;
  stats.numMIRNonTracingBlocks += numMIRNonTracingBBs;
  stats.numMIRNonTracingInstructions += numMIRNonTracingInsts;

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
      csvFile << "function_name,basicblock_id,has_tracing_call,number_of_instructions,instructions\n";
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
      errs() << "Error: Could not open CSV file for appending: " << CSV_OUTPUT_PATH << "\n";
      return false;
    }
    csvHeaderWritten = true;
  }

  if (csvFile.is_open()) {
    // Write basic block information for this function only
    // Create a temporary list of blocks just for this function
    std::vector<BasicBlockInfo> currentFunctionBlocks;
    for (const auto &bbInfo : basicBlockInfoList) {
      if (bbInfo.functionName == functionName) {
        currentFunctionBlocks.push_back(bbInfo);
      }
    }
    
    // Write the blocks for the current function
    for (const auto &bbInfo : currentFunctionBlocks) {
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

      csvFile << escapedFunctionName << ","
              << escapedBasicBlockId << ","
              << (bbInfo.hasTracingCall ? "true" : "false") << ","
              << bbInfo.instructions.size() << ","
              << escapedInstructions << "\n";
    }
    
    // Clear the blocks for this function from the main list to avoid duplicates
    basicBlockInfoList.erase(
      std::remove_if(basicBlockInfoList.begin(), basicBlockInfoList.end(),
        [&functionName](const BasicBlockInfo& bbInfo) {
          return bbInfo.functionName == functionName;
        }),
      basicBlockInfoList.end());
    
    csvFile.close();
  }

  return false;
}

IRAnalysisPass::~IRAnalysisPass() {
  // Print header based on analysis mode
  switch (ANALYSIS_MODE) {
    case AnalysisMode::TRACING_BLOCKS_ONLY:
      errs() << "=== IR Analysis Pass Statistics (Tracing Blocks Only) ===\n\n";
      break;
    case AnalysisMode::NON_TRACING_BLOCKS_ONLY:
      errs() << "=== IR Analysis Pass Statistics (Non-Tracing Blocks Only) ===\n\n";
      break;
    case AnalysisMode::BOTH:
      errs() << "=== IR Analysis Pass Statistics (Tracing vs Non-Tracing Blocks) ===\n\n";
      break;
  }

  for (const auto &entry : moduleStats) {
    const std::string &moduleName = entry.first;
    const ModuleStats &stats = entry.second;

    // Calculate averages for all blocks
    double avgIRInstsPerBlock =
        stats.numIRBasicBlocks > 0
            ? static_cast<double>(stats.numIRInstructions) / stats.numIRBasicBlocks
            : 0.0;
    double avgMIRInstsPerBlock =
        stats.numMIRBasicBlocks > 0
            ? static_cast<double>(stats.numMIRInstructions) / stats.numMIRBasicBlocks
            : 0.0;

    // Calculate averages for tracing blocks
    double avgIRTracingInstsPerBlock =
        stats.numIRTracingBlocks > 0
            ? static_cast<double>(stats.numIRTracingInstructions) / stats.numIRTracingBlocks
            : 0.0;
    double avgMIRTracingInstsPerBlock =
        stats.numMIRTracingBlocks > 0
            ? static_cast<double>(stats.numMIRTracingInstructions) / stats.numMIRTracingBlocks
            : 0.0;

    // Calculate averages for non-tracing blocks
    double avgIRNonTracingInstsPerBlock =
        stats.numIRNonTracingBlocks > 0
            ? static_cast<double>(stats.numIRNonTracingInstructions) / stats.numIRNonTracingBlocks
            : 0.0;
    double avgMIRNonTracingInstsPerBlock =
        stats.numMIRNonTracingBlocks > 0
            ? static_cast<double>(stats.numMIRNonTracingInstructions) / stats.numMIRNonTracingBlocks
            : 0.0;

    errs() << "Module: " << moduleName << "\n";
    
    // Print statistics based on analysis mode
    if (ANALYSIS_MODE == AnalysisMode::TRACING_BLOCKS_ONLY) {
      errs() << "  AOT IR Statistics (Tracing Blocks Only):\n"
             << "    Tracing Blocks: " << stats.numIRBasicBlocks << "\n"
             << "    Tracing Block Instructions: " << stats.numIRInstructions << "\n"
             << "    Average Instructions per Tracing Block: " << format("%.2f", avgIRInstsPerBlock) << "\n"
             << "  \n"
             << "  MIR Statistics (Tracing Blocks Only):\n"
             << "    Tracing Blocks: " << stats.numMIRBasicBlocks << "\n"
             << "    Tracing Block Instructions: " << stats.numMIRInstructions << "\n"
             << "    Average Instructions per Tracing Block: " << format("%.2f", avgMIRInstsPerBlock) << "\n\n";
    } else if (ANALYSIS_MODE == AnalysisMode::NON_TRACING_BLOCKS_ONLY) {
      errs() << "  AOT IR Statistics (Non-Tracing Blocks Only):\n"
             << "    Non-Tracing Blocks: " << stats.numIRBasicBlocks << "\n"
             << "    Non-Tracing Block Instructions: " << stats.numIRInstructions << "\n"
             << "    Average Instructions per Non-Tracing Block: " << format("%.2f", avgIRInstsPerBlock) << "\n"
             << "  \n"
             << "  MIR Statistics (Non-Tracing Blocks Only):\n"
             << "    Non-Tracing Blocks: " << stats.numMIRBasicBlocks << "\n"
             << "    Non-Tracing Block Instructions: " << stats.numMIRInstructions << "\n"
             << "    Average Instructions per Non-Tracing Block: " << format("%.2f", avgMIRInstsPerBlock) << "\n\n";
    } else { // BOTH
      errs() << "  AOT IR Statistics:\n"
             << "    Total Basic Blocks: " << stats.numIRBasicBlocks << "\n"
             << "    Total Instructions: " << stats.numIRInstructions << "\n"
             << "    Average Instructions per Block: " << format("%.2f", avgIRInstsPerBlock) << "\n"
             << "    \n"
             << "    Tracing Blocks: " << stats.numIRTracingBlocks << "\n"
             << "    Tracing Block Instructions: " << stats.numIRTracingInstructions << "\n"
             << "    Average Instructions per Tracing Block: " << format("%.2f", avgIRTracingInstsPerBlock) << "\n"
             << "    \n"
             << "    Non-Tracing Blocks: " << stats.numIRNonTracingBlocks << "\n"
             << "    Non-Tracing Block Instructions: " << stats.numIRNonTracingInstructions << "\n"
             << "    Average Instructions per Non-Tracing Block: " << format("%.2f", avgIRNonTracingInstsPerBlock) << "\n"
             << "  \n"
             << "  MIR Statistics:\n"
             << "    Total Basic Blocks: " << stats.numMIRBasicBlocks << "\n"
             << "    Total Instructions: " << stats.numMIRInstructions << "\n"
             << "    Average Instructions per Block: " << format("%.2f", avgMIRInstsPerBlock) << "\n"
             << "    \n"
             << "    Tracing Blocks: " << stats.numMIRTracingBlocks << "\n"
             << "    Tracing Block Instructions: " << stats.numMIRTracingInstructions << "\n"
             << "    Average Instructions per Tracing Block: " << format("%.2f", avgMIRTracingInstsPerBlock) << "\n"
             << "    \n"
             << "    Non-Tracing Blocks: " << stats.numMIRNonTracingBlocks << "\n"
             << "    Non-Tracing Block Instructions: " << stats.numMIRNonTracingInstructions << "\n"
             << "    Average Instructions per Non-Tracing Block: " << format("%.2f", avgMIRNonTracingInstsPerBlock) << "\n\n";
    }
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

  // CSV file was written incrementally during pass execution
  if (csvHeaderWritten) {
    switch (ANALYSIS_MODE) {
      case AnalysisMode::TRACING_BLOCKS_ONLY:
        errs() << "\nBasic block information (tracing blocks only) written to: " << CSV_OUTPUT_PATH << "\n";
        break;
      case AnalysisMode::NON_TRACING_BLOCKS_ONLY:
        errs() << "\nBasic block information (non-tracing blocks only) written to: " << CSV_OUTPUT_PATH << "\n";
        break;
      case AnalysisMode::BOTH:
        errs() << "\nBasic block information (tracing and non-tracing) written to: " << CSV_OUTPUT_PATH << "\n";
        break;
    }
    errs() << "Total basic blocks processed: " << basicBlockInfoList.size() << "\n";
  }
}

char IRAnalysisPass::ID = 0;
INITIALIZE_PASS(IRAnalysisPass, "ir-analysis-pass", "IR Analysis Pass", false, false)

namespace llvm {
MachineFunctionPass *createIRAnalysisPass() { return new IRAnalysisPass(); }
} // namespace llvm

