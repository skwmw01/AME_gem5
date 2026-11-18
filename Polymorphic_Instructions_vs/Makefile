SHELL := /bin/bash
.DELETE_ON_ERROR:
ROOT := $(abspath ..)
COMMON := $(ROOT)/example/common
TOOLCHAIN ?= $(ROOT)/toolchain/install
CLANG ?= $(TOOLCHAIN)/bin/clang
OBJDUMP ?= $(TOOLCHAIN)/bin/llvm-objdump
MODE := $(shell cat $(TOOLCHAIN)/.ame_toolchain_mode 2>/dev/null)
ifeq ($(MODE),source)
ARCH := rv64gv_boscztt
PROFILE := -mboscztt-profile=ame-gem5
FEATURE := +boscztt,+boscztt-ame-gem5
else
ARCH := rv64gv_xxiangshanztt
FEATURE := +xxiangshanztt
endif
CFLAGS := -target riscv64-unknown-elf -march=$(ARCH) $(PROFILE) \
 -mabi=lp64d -O2 -g -Wall -Wextra -Werror -ffreestanding -fno-builtin \
 -mcmodel=medany -mno-relax -fno-vectorize -fno-slp-vectorize \
 -ffp-contract=off -ffunction-sections -fdata-sections -I$(COMMON)/include
LDFLAGS := -fuse-ld=lld -nostdlib -static -Wl,--gc-sections,--no-relax,-T,$(COMMON)/link.ld
LIBGCC ?= $(TOOLCHAIN)/riscv64-unknown-elf/gcc/libgcc.a
PYTHON ?= python3

.PHONY: all smoke run analyze tools clean
all: build/experiment.elf build/experiment.dis build/experiment.symbols

build:
	mkdir -p $@

build/experiment.elf: driver.c kernels.S Makefile $(COMMON)/runtime.c $(COMMON)/crt0.S $(COMMON)/link.ld | build
	$(CLANG) $(CFLAGS) $(COMMON)/crt0.S $(COMMON)/runtime.c driver.c kernels.S $(LDFLAGS) $(LIBGCC) -o $@

build/experiment.dis: build/experiment.elf
	$(OBJDUMP) -d --mattr=$(FEATURE) $< > $@

build/experiment.symbols: build/experiment.elf
	$(OBJDUMP) -t $< > $@

smoke: all
	$(PYTHON) run.py --smoke

run: all
	$(PYTHON) run.py

analyze: all
	$(PYTHON) analyze.py build/full

tools:
	@printf '%s\n' '$(CLANG)' '$(OBJDUMP)' '$(TOOLCHAIN)/bin/ld.lld' '$(LIBGCC)'

clean:
	$(RM) -r build
