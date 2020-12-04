TARGET = zcu104fw
# SOURCES := $(wildcard *.c)
SOURCES := main.c pl_mmap.c udp_server.c

CC := aarch64-linux-gnu-gcc
CFLAGS := -Og -g -Wall -Wextra

BUILD_DIR = build
OBJECTS := $(SOURCES:%.c=$(BUILD_DIR)/%.o)

$(TARGET): $(OBJECTS)
	@printf "%-6s %s\n" [LD] $(notdir $@)
	$(CC) $(LDFLAGS) -o $(TARGET) $^

$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(dir $@)
	@printf "%-6s %s\n" [CC] $(notdir $@)
	$(CC) $(CFLAGS) -MD -MP -MF ${@:.o=.d} -c -o $@ $<

clean:
	rm -rf $(BUILD_DIR) $(TARGET)

# pull in dependency info for existing .o files
-include $(OBJECTS:.o=.d)

# Silent makefile as proposed in:
# http://make.mad-scientist.net/managing-recipe-echoing/
# running `make VERBOSE=1` or `make V=1` will print all commands
$(VERBOSE)$(V).SILENT:
