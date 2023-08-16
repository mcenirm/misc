usage:
	$(error Usage: make Foo.bash)

JAVA := java
JAVAC := javac
ifneq ($(JAVA_HOME),)
export PATH := $(JAVA_HOME)/bin:$(PATH)
JAVA := $(JAVA_HOME)/bin/$(JAVA)
JAVAC := $(JAVA_HOME)/bin/$(JAVAC)
endif

%.class : %.java
	$(JAVAC) $<

%.bash : %.class Makefile
	echo '$(JAVA) -cp $(PWD) $(basename $<) "$$@"' > $@
	chmod +x $@

.PRECIOUS : %.class
