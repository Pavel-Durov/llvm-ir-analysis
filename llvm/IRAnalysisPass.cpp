//===----------------------------------------------------------------------===//
//
// IR Analysis Pass
//
// This pass collects statistics about AOT IR (LLVM IR) and MIR (Machine IR)
// during compilation and outputs detailed basic block information to a CSV file.
//
// CSV Output Format:
//   The pass generates a CSV file containing per-basic-block data with columns:
//   - function_name: Name of the function containing the basic block
//   - basicblock_id: Basic block identifier (e.g., BB#0, BB#1)
//   - number_of_instructions: Count of executable instructions in the block
//   - instructions: Newline-separated list of instruction strings
//
// Instruction Counting:
//   Only actual executable machine instructions that will become assembly code
//   are counted. The following are explicitly excluded:
//   - Debug instructions (DBG_VALUE, DBG_LABEL, DBG_PHI, etc.)
//   - Pseudo-instructions that do not correspond to real machine instructions
//   - Meta instructions that produce no executable output
//   - Position markers (EH/GC labels and CFI instructions for unwinding)
//   - Profiling pseudo-probes for instrumentation
//   - Stack frame management pseudo-operations (FrameSetup/FrameDestroy)
//
//===----------------------------------------------------------------------===//

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
      // Only count actual executable machine instructions that will become assembly code.
      // Exclude:
      //  - isDebugInstr(): debug information (DBG_VALUE, DBG_LABEL, etc.)
      //  - isPseudo(): pseudo-instructions that do not correspond to real machine instructions
      //  - isMetaInstruction(): instructions that do not produce any executable output
      //  - isPosition(): position markers (EH/GC labels and CFI instructions for unwinding)
      //  - isPseudoProbe(): profiling pseudo-probes for instrumentation
      //  - FrameSetup/FrameDestroy: stack frame management pseudo-operations
      if (!MI.isDebugInstr() && !MI.isPseudo() && !MI.isMetaInstruction() &&
          !MI.isPosition() && !MI.isPseudoProbe() &&
          !MI.getFlag(MachineInstr::FrameSetup) &&
          !MI.getFlag(MachineInstr::FrameDestroy)) {
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
      csvFile << "function_name,basicblock_id,number_of_instructions,instructions\n";
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
    // Write basic block information for this function
    for (const auto &bbInfo : basicBlockInfoList) {
      // Only write if it belongs to the current function
      if (bbInfo.functionName == functionName) {
        std::string escapedFunctionName = escapeCSVField(bbInfo.functionName);
        std::string escapedBasicBlockId = escapeCSVField(bbInfo.basicBlockId);

        // Join instructions with newline separator
        std::string instructionsStr;
        for (size_t i = 0; i < bbInfo.instructions.size(); ++i) {
          if (i > 0) {
            instructionsStr += "\n";
          }
          instructionsStr += bbInfo.instructions[i];
        }
        std::string escapedInstructions = escapeCSVField(instructionsStr);

        csvFile << escapedFunctionName << ","
                << escapedBasicBlockId << ","
                << bbInfo.instructions.size() << ","
                << escapedInstructions << "\n";
      }
    }
    csvFile.close();
  }

  return false;
}

IRAnalysisPass::~IRAnalysisPass() {
  errs() << "=== IR Analysis Pass Statistics ===\n\n";

  for (const auto &entry : moduleStats) {
    const std::string &moduleName = entry.first;
    const ModuleStats &stats = entry.second;

    double avgIRInstsPerBlock =
        stats.numIRBasicBlocks > 0
            ? static_cast<double>(stats.numIRInstructions) / stats.numIRBasicBlocks
            : 0.0;

    double avgMIRInstsPerBlock =
        stats.numMIRBasicBlocks > 0
            ? static_cast<double>(stats.numMIRInstructions) / stats.numMIRBasicBlocks
            : 0.0;

    errs() << "Module: " << moduleName << "\n"
           << "  AOT IR Statistics:\n"
           << "    Total Basic Blocks: " << stats.numIRBasicBlocks << "\n"
           << "    Total Instructions: " << stats.numIRInstructions << "\n"
           << "    Average Instructions per Block: " << avgIRInstsPerBlock << "\n"
           << "  MIR Statistics:\n"
           << "    Total Basic Blocks: " << stats.numMIRBasicBlocks << "\n"
           << "    Total Instructions: " << stats.numMIRInstructions << "\n"
           << "    Average Instructions per Block: " << avgMIRInstsPerBlock << "\n\n";
  }
  errs() << "===========================\n";

  // Print address-taken functions if enabled
  if (CountAddressTakenFunctions && !addressTakenFunctions.empty()) {
    errs() << "\n=== Address-Taken Functions ===\n";
    errs() << "Total: " << addressTakenFunctions.size() << "\n";
    for (const auto &funcName : addressTakenFunctions) {
      errs() << "  " << funcName << ";";
    }
    errs() << "==============================\n";
  }

  // CSV file was written incrementally during pass execution
  if (csvHeaderWritten) {
    errs() << "\nBasic block information written to: " << CSV_OUTPUT_PATH << "\n";
    errs() << "Total basic blocks processed: " << basicBlockInfoList.size() << "\n";
  }
}

char IRAnalysisPass::ID = 0;
INITIALIZE_PASS(IRAnalysisPass, "ir-analysis-pass", "IR Analysis Pass", false, false)

namespace llvm {
MachineFunctionPass *createIRAnalysisPass() { return new IRAnalysisPass(); }
} // namespace llvm

