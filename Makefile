CHORDPRO     := chordpro
PROJECT_CFG  := chordpro-ukulele.json
SONGBOOKS    := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard songbooks/*/*.cho)))))
PDF_DIR      := pdf
PDFS         := $(foreach sb,$(SONGBOOKS),$(PDF_DIR)/$(sb).pdf)

.PHONY: all clean $(SONGBOOKS)

all: $(SONGBOOKS)

$(PDF_DIR):
	mkdir -p $(PDF_DIR)

# Target per songbook slug: make bricioline, make bricioline-en, etc.
define SONGBOOK_RULE
$(1): $(PDF_DIR)/$(1).pdf

$(PDF_DIR)/$(1).pdf: songbooks/$(1)/*.cho | $(PDF_DIR)
	$(CHORDPRO) --config $(PROJECT_CFG) $$^ -o $$@
endef

$(foreach sb,$(SONGBOOKS),$(eval $(call SONGBOOK_RULE,$(sb))))

clean:
	rm -f $(PDFS)
