SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
BUILDDIR      = build

help:
	@$(SPHINXBUILD) -M help . "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

%: Makefile
	@$(SPHINXBUILD) -M $@ . "$(BUILDDIR)" $(SPHINXOPTS) $(O)
