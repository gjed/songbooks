CHORDPRO     := chordpro
PROJECT_CFG  := chordpro-ukulele.json
SONGBOOKS    := $(notdir $(wildcard songbooks/*))
PDFS         := $(foreach sb,$(SONGBOOKS),songbooks/$(sb)/$(sb).pdf)

.PHONY: all clean $(SONGBOOKS)

all: $(SONGBOOKS)

# Target per songbook slug: make bricioline, make bricioline-en, etc.
define SONGBOOK_RULE
$(1): songbooks/$(1)/$(1).pdf

songbooks/$(1)/$(1).pdf: songbooks/$(1)/*.cho
	$(CHORDPRO) --config $(PROJECT_CFG) $$^ -o $$@
endef

$(foreach sb,$(SONGBOOKS),$(eval $(call SONGBOOK_RULE,$(sb))))

clean:
	rm -f $(PDFS)
