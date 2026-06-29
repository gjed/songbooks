CHORDPRO     := chordpro
PROJECT_CFG  := chordpro-ukulele.json
COVER_CFG    := chordpro-cover.json
SONGBOOKS    := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard songbooks/*/*.cho)))))
PDF_DIR      := pdf
PDFS         := $(foreach sb,$(SONGBOOKS),$(PDF_DIR)/$(sb).pdf)
GS           := gs

.PHONY: all clean $(SONGBOOKS)

all: $(SONGBOOKS)

$(PDF_DIR):
	mkdir -p $(PDF_DIR)

# Check if a songbook has cover pages (00-cover.cho, 01-chord-chart.cho, 99-back-cover.cho)
COVER_FILES = 00-cover.cho 01-chord-chart.cho 99-back-cover.cho

# Song files = all .cho files except cover/special pages
SONG_FILES   = $(filter-out $(COVER_FILES),$(notdir $(wildcard $(1)/*.cho)))
COVER_EXISTS = $(wildcard $(1)/$(2))

# Target per songbook slug: make bricioline, make bricioline-en, etc.
define SONGBOOK_RULE
$(1): $(PDF_DIR)/$(1).pdf

ifeq ($$(strip $$(call COVER_EXISTS,songbooks/$(1),00-cover.cho)),)
# No cover — render everything normally
$(PDF_DIR)/$(1).pdf: songbooks/$(1)/*.cho | $(PDF_DIR)
	$(CHORDPRO) --config $(PROJECT_CFG) $$^ -o $$@
else
# Has cover pages — render separately and merge
COVER_SRCS_$(1) := $$(foreach f,$(COVER_FILES),$$(wildcard songbooks/$(1)/$$(f)))
SONG_SRCS_$(1)  := $$(wildcard songbooks/$(1)/*.cho)
SONG_ONLY_$(1)  := $$(filter-out $$(COVER_SRCS_$(1)),$$(SONG_SRCS_$(1)))

$(PDF_DIR)/$(1)-covers.pdf: $$(COVER_SRCS_$(1)) | $(PDF_DIR)
	$(CHORDPRO) --config $(COVER_CFG) $$^ -o $$@

$(PDF_DIR)/$(1)-songs.pdf: $$(SONG_ONLY_$(1)) | $(PDF_DIR)
	$(CHORDPRO) --config $(PROJECT_CFG) $$^ -o $$@

$(PDF_DIR)/$(1).pdf: $(PDF_DIR)/$(1)-covers.pdf $(PDF_DIR)/$(1)-songs.pdf
	$(GS) -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite \
	  -sOutputFile=$$@ \
	  $(PDF_DIR)/$(1)-covers.pdf $(PDF_DIR)/$(1)-songs.pdf
	rm -f $(PDF_DIR)/$(1)-covers.pdf $(PDF_DIR)/$(1)-songs.pdf
endif
endef

$(foreach sb,$(SONGBOOKS),$(eval $(call SONGBOOK_RULE,$(sb))))

clean:
	rm -f $(PDFS) $(PDF_DIR)/*-covers.pdf $(PDF_DIR)/*-songs.pdf
