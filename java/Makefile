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

JAVA_FILES := $(wildcard *.java)
BASH_FILES := $(JAVA_FILES:.java=.bash)

define USAGE
Found targets:

 $(foreach b,$(BASH_FILES),make $(b)
)

endef

usage:
	$(error $(USAGE))

all : $(BASH_FILES)

%.class : %.java
	$(RM) -v -- $@ $(foreach f,$(wildcard $*$$*.class),'$(f)')
	$(JAVAC) $<

%.bash : %.class Makefile
	echo '$(PREFACE) $(JAVA) -cp $(PWD) $* "$$@"' > $@
	chmod +x $@

.PRECIOUS : %.class
