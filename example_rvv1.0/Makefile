SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
CASES := gemm_fp32 gemm_int8 gemm_mixed gemm_mixed_source_types gelu softmax mha ffn rope rmsnorm
.DEFAULT_GOAL := help
.PHONY: help build test report clean test-vlens test-tail $(CASES) $(addprefix build-,$(CASES)) $(addprefix test-,$(CASES))
.NOTPARALLEL: test
help:
	@echo "RVV 1.0 operators: make build | test | <case> | test-vlens | test-tail"
	@echo "Clang 18+ and LLD, standard rv64gcv, gem5 RiscvMinorCPU"
	@echo "Overrides: CLANG=... LLVM_OBJDUMP=... GEM5=... VLEN=128|256|512|1024"
build: $(addprefix build-,$(CASES))
test: $(addprefix test-,$(CASES)) report
$(CASES):
	+$(MAKE) --no-print-directory -C $@ test
$(addprefix build-,$(CASES)): build-%:
	+$(MAKE) --no-print-directory -C $* all
$(addprefix test-,$(CASES)): test-%:
	+$(MAKE) --no-print-directory -C $* test
report:
	python3 common/write_report.py suite --output build/reports/EXAMPLE_REPORT.md $(foreach case,$(CASES),$(case)/build/reports/REPORT.md)
test-vlens:
	+$(MAKE) test VLEN=128
	cp build/reports/EXAMPLE_REPORT.md build/reports/VLEN128_REPORT.md
	+$(MAKE) test VLEN=512
	cp build/reports/EXAMPLE_REPORT.md build/reports/VLEN512_REPORT.md
	+$(MAKE) test VLEN=256
	cp build/reports/EXAMPLE_REPORT.md build/reports/VLEN256_REPORT.md
test-tail:
	python3 common/test_tail.py
clean:
	@for case in $(CASES); do $(MAKE) --no-print-directory -C $$case clean; done
	rm -rf build
