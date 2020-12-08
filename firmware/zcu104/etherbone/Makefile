TARGET := zcu104_etherbone
SOURCES := $(wildcard *.c)

DEBUG ?= 0
ifeq ($(DEBUG),1)
OPTIM := -Og -g
else
OPTIM := -O2 -DNDEBUG
endif

CC := aarch64-linux-gnu-gcc
CFLAGS := $(OPTIM) -Wall -Wextra -Werror

BUILD_DIR = build
OBJECTS := $(SOURCES:%.c=$(BUILD_DIR)/%.o)

all: $(BUILD_DIR)/$(TARGET)

$(BUILD_DIR)/$(TARGET): $(OBJECTS)
	@printf "%-6s %s\n" [LD] $(notdir $@)
	$(CC) $(LDFLAGS) -o $(BUILD_DIR)/$(TARGET) $^

$(BUILD_DIR)/%.o: %.c Makefile
	@mkdir -p $(dir $@)
	@printf "%-6s %s\n" [CC] $(notdir $@)
	$(CC) $(CFLAGS) -MD -MP -MF ${@:.o=.d} -c -o $@ $<

clean:
	rm -rf $(BUILD_DIR)

# pull in dependency info for existing .o files
-include $(OBJECTS:.o=.d)

# Silent makefile as proposed in:
# http://make.mad-scientist.net/managing-recipe-echoing/
# running `make VERBOSE=1` or `make V=1` will print all commands
$(VERBOSE)$(V).SILENT:
