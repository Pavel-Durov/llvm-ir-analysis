#ifndef LLVM_CODEGEN_IRANALYSISPASS_H
#define LLVM_CODEGEN_IRANALYSISPASS_H

namespace llvm {

class MachineFunctionPass;

// Factory function to create the pass
MachineFunctionPass *createIRAnalysisPass();

} // namespace llvm

#endif // LLVM_CODEGEN_IRANALYSISPASS_H

