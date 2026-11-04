#
# Copyright (c) 2026 BOSC & ICT, CAS
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:

ifndef CASE_BINARY
$(error CASE_BINARY must be set before including common/case_rules.mk)
endif
ifndef CASE_DESCRIPTION
$(error CASE_DESCRIPTION must be set before including common/case_rules.mk)
endif
ifndef REQUIRED_MNEMONICS
$(error REQUIRED_MNEMONICS must be set before including common/case_rules.mk)
endif

CASE_DIR := $(CURDIR)
EXAMPLE_ROOT := $(abspath $(CASE_DIR)/..)
AMEGEM5_ROOT := $(abspath $(EXAMPLE_ROOT)/..)
COMMON_DIR := $(EXAMPLE_ROOT)/common
RUNTIME_DIR := $(EXAMPLE_ROOT)/common

BUILD_DIR ?= $(CASE_DIR)/build
HOST_DIR := $(BUILD_DIR)/host
TARGET_DIR := $(BUILD_DIR)/target
REPORT_DIR := $(BUILD_DIR)/reports
DISASM_DIR := $(BUILD_DIR)/disasm
LOG_DIR := $(BUILD_DIR)/logs
M5OUT_DIR := $(BUILD_DIR)/m5out
GENERATED_DIR := $(BUILD_DIR)/generated
BUILD_CONFIG := $(GENERATED_DIR)/build-config.txt

SOURCE := $(CASE_DIR)/main.c
OPERATOR_SOURCE := $(CASE_DIR)/operators.c
SOURCES := $(SOURCE) $(OPERATOR_SOURCE) $(COMMON_DIR)/rvv_kernels.c
HOST_BINARY := $(HOST_DIR)/$(CASE_BINARY)
TARGET_BINARY := $(TARGET_DIR)/$(CASE_BINARY)
HOST_REPORT := $(REPORT_DIR)/$(CASE_BINARY).host.txt
MINOR_REPORT := $(REPORT_DIR)/$(CASE_BINARY).minor.txt
CASE_REPORT := $(REPORT_DIR)/REPORT.md
DISASSEMBLY := $(DISASM_DIR)/$(CASE_BINARY).dis
CASE_DISPLAY := $(patsubst test_llm_%,%,$(CASE_BINARY))

# Validation modes:
#   GOLDEN=host       compare MinorCPU with the host C implementation
#   GOLDEN=reference  compare MinorCPU with MATRIX_REFERENCE
#
# Cases with the conventional config files default to the external reference.
# If the reference is not available, keep the test runnable with the Host C
# golden.  Command-line values still override these defaults.
DEFAULT_MATRIX_INPUT := $(CASE_DIR)/config/matrix_input.json
DEFAULT_MATRIX_REFERENCE := $(CASE_DIR)/config/matrix_reference.json
MATRIX_INPUT ?= $(if $(wildcard $(DEFAULT_MATRIX_INPUT)),$(DEFAULT_MATRIX_INPUT),)
MATRIX_REFERENCE ?= $(if $(wildcard $(DEFAULT_MATRIX_REFERENCE)),$(DEFAULT_MATRIX_REFERENCE),)
GOLDEN ?= $(if $(and $(MATRIX_INPUT),$(wildcard $(MATRIX_REFERENCE))),reference,host)

ifneq ($(filter $(GOLDEN),host reference),$(GOLDEN))
$(error GOLDEN must be either host or reference)
endif

ifneq ($(strip $(MATRIX_INPUT)),)
override MATRIX_INPUT := $(abspath $(MATRIX_INPUT))
MATRIX_HEADER := $(GENERATED_DIR)/ztt_matrix_input.h
MATRIX_BUILD_FLAGS := -DZTT_EXTERNAL_MATRIX_INPUT -include $(MATRIX_HEADER)
GENERATED_HEADERS := $(MATRIX_HEADER)
endif

ifeq ($(GOLDEN),reference)
ifeq ($(strip $(MATRIX_INPUT)),)
$(error GOLDEN=reference requires MATRIX_INPUT=/path/to/input.json)
endif
override MATRIX_REFERENCE := $(if $(strip $(MATRIX_REFERENCE)),$(abspath $(MATRIX_REFERENCE)),)
REFERENCE_REPORT := $(REPORT_DIR)/$(CASE_BINARY).reference.txt
GOLDEN_REPORT := $(REFERENCE_REPORT)
GOLDEN_LABEL := External reference
RUN_DEPENDENCIES := $(REFERENCE_REPORT) $(MINOR_REPORT)
else
GOLDEN_REPORT := $(HOST_REPORT)
GOLDEN_LABEL := Host C golden
RUN_DEPENDENCIES := $(HOST_REPORT) $(MINOR_REPORT)
endif

HOST_CC ?= $(CC)
# Standard RVV 1.0 toolchain: no AME compiler, C library or libgcc required.
CLANG_ROOT ?= $(AMEGEM5_ROOT)/toolchain/install
CLANG ?= $(or $(wildcard $(CLANG_ROOT)/bin/clang),$(shell command -v clang-18 2>/dev/null),$(shell command -v clang 2>/dev/null))
LLVM_OBJDUMP ?= $(or $(wildcard $(CLANG_ROOT)/bin/llvm-objdump),$(shell command -v llvm-objdump-18 2>/dev/null),$(shell command -v llvm-objdump 2>/dev/null))
CLANG_RESOURCE_DIR ?= $(shell "$(CLANG)" -print-resource-dir 2>/dev/null)
TARGET_MARCH := rv64gcv
TARGET_OBJDUMP_FEATURE := +v
TARGET_LD_MODE ?= -fuse-ld=lld
VLEN ?= 256
MAX_TICKS ?= 1000000000000
RUN_TIMEOUT ?= 180
EXTRA_CFLAGS ?=

GEM5 ?= $(if $(AMEGEM5_GEM5),$(AMEGEM5_GEM5),$(AMEGEM5_ROOT)/build/RISCV/gem5.opt)
MEM_SIZE ?= 128MiB
VECTOR_OP_LAT ?= 6

COMMON_HEADERS := $(wildcard $(COMMON_DIR)/*.h)
RUNTIME_SOURCES := $(RUNTIME_DIR)/crt0.S $(RUNTIME_DIR)/runtime.c
RUNTIME_HEADERS := $(wildcard $(RUNTIME_DIR)/include/*.h)

HOST_CFLAGS := -ffp-contract=off $(EXTRA_CFLAGS) -O2 -g -Wall -Wextra -Werror -I$(COMMON_DIR) $(MATRIX_BUILD_FLAGS)
TARGET_CFLAGS := \
	-target riscv64-unknown-elf \
	-resource-dir $(CLANG_RESOURCE_DIR) \
	-march=$(TARGET_MARCH) \
	-mabi=lp64d \
	$(EXTRA_CFLAGS) -O2 -g -Wall -Wextra -Werror \
	-ffreestanding -fno-builtin -mcmodel=medany \
	-ffunction-sections -fdata-sections \
	-fno-vectorize -fno-slp-vectorize -ffp-contract=off \
	-I$(COMMON_DIR) -I$(RUNTIME_DIR)/include $(MATRIX_BUILD_FLAGS)
TARGET_LDFLAGS := \
	$(TARGET_LD_MODE) \
	-nostdlib -static \
	-Wl,-T,$(RUNTIME_DIR)/link.ld \
	-Wl,--gc-sections

.DEFAULT_GOAL := all
.PHONY: all test test-host run audit report clean force check-host-tools check-target-tools check-gem5

force:

all: $(HOST_BINARY) $(TARGET_BINARY) audit

test-host: $(HOST_REPORT)

test:
	@echo "[TEST] $(CASE_DISPLAY): $(CASE_DESCRIPTION)"
	+$(MAKE) --no-print-directory report

run: $(RUN_DEPENDENCIES)
	@mkdir -p $(LOG_DIR)
	@if cmp -s $(GOLDEN_REPORT) $(MINOR_REPORT); then \
		rm -f $(LOG_DIR)/golden-minor.diff; \
		echo "[PASS] $(CASE_DISPLAY): MinorCPU == $(GOLDEN_LABEL)"; \
	else \
		diff -u $(GOLDEN_REPORT) $(MINOR_REPORT) | tee $(LOG_DIR)/golden-minor.diff; \
		exit 1; \
	fi

audit: $(DISASSEMBLY)
	python3 $(COMMON_DIR)/audit.py $(DISASSEMBLY) $(REQUIRED_MNEMONICS)

report: run audit
	python3 $(COMMON_DIR)/write_report.py case \
		--name $(CASE_BINARY) \
		--description "$(CASE_DESCRIPTION); VLEN=$(VLEN), ELEN=64" \
		--source "$(notdir $(SOURCE)) + $(notdir $(OPERATOR_SOURCE)) + common/rvv_kernels.c" \
		--golden $(GOLDEN_REPORT) \
		--golden-label "$(GOLDEN_LABEL)" \
		--minor $(MINOR_REPORT) \
		--output $(CASE_REPORT)
	@echo "[PASS] $(CASE_DISPLAY): report $(CASE_REPORT)"

check-host-tools:
	@command -v "$(HOST_CC)" >/dev/null 2>&1 || test -x "$(HOST_CC)" || { \
		echo "[FAIL] host compiler not found: $(HOST_CC)"; exit 1; }

check-target-tools:
	@test -x "$(CLANG)" || { echo "[FAIL] set CLANG_ROOT or CLANG"; exit 1; }
	@test -x "$(LLVM_OBJDUMP)" || { echo "[FAIL] set CLANG_ROOT or LLVM_OBJDUMP"; exit 1; }
	@test -d "$(CLANG_RESOURCE_DIR)" || { echo "[FAIL] set CLANG_RESOURCE_DIR"; exit 1; }

check-gem5:
	@test -x "$(GEM5)" || { echo "[FAIL] gem5 not found: $(GEM5)"; exit 1; }

ifeq ($(NO_BUILD),1)
$(HOST_BINARY):
	@test -x $@ || { echo "[FAIL] --no-build binary is missing: $@"; exit 1; }

$(TARGET_BINARY):
	@test -f $@ || { echo "[FAIL] --no-build binary is missing: $@"; exit 1; }
else
$(HOST_BINARY): $(SOURCES) $(COMMON_HEADERS) $(GENERATED_HEADERS) $(BUILD_CONFIG) | check-host-tools
	@mkdir -p $(HOST_DIR) $(LOG_DIR)
	$(HOST_CC) $(HOST_CFLAGS) $(SOURCES) $(HOST_LDLIBS) -o $@ 2>&1 | tee $(LOG_DIR)/host-build.log

$(TARGET_BINARY): $(SOURCES) $(COMMON_HEADERS) $(GENERATED_HEADERS) $(BUILD_CONFIG) $(RUNTIME_SOURCES) $(RUNTIME_HEADERS) $(RUNTIME_DIR)/link.ld | check-target-tools
	@mkdir -p $(TARGET_DIR) $(LOG_DIR)
	$(CLANG) $(TARGET_CFLAGS) $(RUNTIME_SOURCES) $(SOURCES) \
		$(TARGET_LDFLAGS) -o $@ 2>&1 | tee $(LOG_DIR)/target-build.log
endif

$(BUILD_CONFIG): force
	@mkdir -p $(GENERATED_DIR)
	@printf '%s\n' \
		'CLANG=$(CLANG)' 'HOST_CC=$(HOST_CC)' \
		'TARGET_CFLAGS=$(TARGET_CFLAGS)' 'HOST_CFLAGS=$(HOST_CFLAGS)' \
		'TARGET_LDFLAGS=$(TARGET_LDFLAGS)' \
		'MATRIX_INPUT=$(MATRIX_INPUT)' \
		'MATRIX_BUILD_FLAGS=$(MATRIX_BUILD_FLAGS)' > $@.tmp
	@if ! cmp -s $@.tmp $@; then cp $@.tmp $@; fi
	@rm -f $@.tmp

ifneq ($(strip $(MATRIX_INPUT)),)
$(MATRIX_HEADER): force $(MATRIX_INPUT) $(COMMON_DIR)/matrix_case.py
	@mkdir -p $(GENERATED_DIR)
	python3 $(COMMON_DIR)/matrix_case.py header \
		--input $(MATRIX_INPUT) --output $@
endif

ifeq ($(GOLDEN),reference)
$(REFERENCE_REPORT): force $(MATRIX_INPUT) $(MATRIX_REFERENCE) $(COMMON_DIR)/matrix_case.py
	@mkdir -p $(REPORT_DIR) $(LOG_DIR)
	python3 $(COMMON_DIR)/matrix_case.py report \
		--input $(MATRIX_INPUT) \
		$(if $(MATRIX_REFERENCE),--reference $(MATRIX_REFERENCE),) \
		--output $@
	@echo "[PASS] $(CASE_DISPLAY): external reference prepared"
endif

$(DISASSEMBLY): $(TARGET_BINARY) | check-target-tools
	@mkdir -p $(DISASM_DIR) $(LOG_DIR)
	$(LLVM_OBJDUMP) -d --mattr=$(TARGET_OBJDUMP_FEATURE) $< > $@

$(HOST_REPORT): force $(HOST_BINARY)
	@mkdir -p $(REPORT_DIR) $(LOG_DIR)
	@rm -f $@
	$(HOST_BINARY) $@ 2>&1 | tee $(LOG_DIR)/host-run.log
	@test -f $@ || { echo "[FAIL] Host report was not generated: $@"; exit 1; }
	@echo "[PASS] $(CASE_DISPLAY): Host"

$(MINOR_REPORT): force $(TARGET_BINARY) | check-gem5
	@mkdir -p $(REPORT_DIR) $(LOG_DIR) $(M5OUT_DIR)
	@rm -f $@
	timeout $(RUN_TIMEOUT) $(GEM5) -d $(M5OUT_DIR) $(EXAMPLE_ROOT)/rvv_config.py \
		--cpu minor --mem-size $(MEM_SIZE) \
		--vlen $(VLEN) --max-ticks $(MAX_TICKS) \
		--vector-op-lat $(VECTOR_OP_LAT) \
		--cmd '$(TARGET_BINARY) $(MINOR_REPORT)' \
		2>&1 | tee $(LOG_DIR)/minor-run.log
	@test -f $@ || { echo "[FAIL] MinorCPU report was not generated: $@"; exit 1; }
	python3 $(COMMON_DIR)/check_execution.py $(M5OUT_DIR)/stats.txt
	@echo "[PASS] $(CASE_DISPLAY): MinorCPU"

clean:
	rm -rf $(BUILD_DIR)
