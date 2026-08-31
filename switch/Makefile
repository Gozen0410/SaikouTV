# Saikou Switch - native homebrew bootstrap

.SUFFIXES:

include $(DEVKITPRO)/libnx/switch_rules

TARGET      := saikou_switch
BUILD       := build
SOURCES     := source
INCLUDES    := include

ARCH        := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS      := -g -Wall -Wextra -Werror -O2 $(ARCH) $(INCLUDE)
CFLAGS      += -D__SWITCH__
CXXFLAGS    := $(CFLAGS) -fno-rtti -fno-exceptions
ASFLAGS     := -g $(ARCH)

LIBS        := -lnx
LIBDIRS     := $(PORTLIBS) $(LIBNX)

export APP_TITLE      := Saikou Switch
export APP_AUTHOR     := SaikouTV Switch Port
export APP_VERSION    := 0.1.0
export APP_DESCRIPTION := Native Switch port bootstrap

#---------------------------------------------------------------------------------
# build
#---------------------------------------------------------------------------------

ifneq ($(BUILD),$(notdir $(CURDIR)))

export TOPDIR := $(CURDIR)
export VPATH := $(foreach dir,$(SOURCES),$(CURDIR)/$(dir))

CFILES   := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
CPPFILES := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp)))
SFILES   := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.s)))

export OFILES_SRC := $(CFILES:.c=.o) $(CPPFILES:.cpp=.o) $(SFILES:.s=.o)
export OFILES     := $(OFILES_SRC:.o=.o)
export INCLUDE    := $(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir))
export LIBPATHS   := $(foreach dir,$(LIBDIRS),-L$(dir)/lib)
export LIBS

.PHONY: all clean

all: $(TARGET).nro

else

DEPENDS := $(OFILES:.o=.d)

$(TARGET).nro: $(TARGET).elf

$(TARGET).elf: $(OFILES)
	@echo linking $(notdir $@)
	@$(LD) $(LDFLAGS) $(OFILES) $(LIBPATHS) $(LIBS) -o $@

%.o: %.c
	@echo $(notdir $<)
	@$(CC) $(CFLAGS) -MMD -MP -c $< -o $@

%.o: %.cpp
	@echo $(notdir $<)
	@$(CXX) $(CXXFLAGS) -MMD -MP -c $< -o $@

-include $(DEPENDS)

endif
