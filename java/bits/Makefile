# If make is not in "silent" mode, then make sure rm is verbose
ifneq (s,$(findstring s,$(word 1, $(MAKEFLAGS))))
RM := $(RM) -v
endif

# If JAVA_HOME is set, then use that for building and running
JAVA := java
JAVAC := javac
ifneq ($(JAVA_HOME),)
export PATH := $(JAVA_HOME)/bin:$(PATH)
JAVA := $(JAVA_HOME)/bin/$(JAVA)
JAVAC := $(JAVA_HOME)/bin/$(JAVAC)
PREFACE := JAVA_HOME=$(JAVA_HOME) PATH=$(JAVA_HOME)/bin:$$PATH
else
PREFACE :=
endif

JAVA_FILES := $(wildcard src/*.java)
BASH_FILES := $(patsubst src/%.java,scripts/%.bash,$(JAVA_FILES))

define USAGE
Found targets:

 $(foreach b,$(BASH_FILES),make $(b)
)

endef

usage:
	$(error $(USAGE))

all : $(BASH_FILES)

classes/%.class : src/%.java
	[ -d classes ] || mkdir classes
	$(RM) -- $@ $(foreach f,$(wildcard classes/$*$$*.class),'$(f)')
	$(JAVAC) -d classes $<

scripts/%.bash : classes/%.class Makefile
	[ -d scripts ] || mkdir scripts
	echo '$(PREFACE) $(JAVA) -cp $(PWD)/classes $* "$$@"' > $@
	chmod +x $@

.PRECIOUS : classes/%.class
