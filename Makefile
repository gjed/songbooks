CHORDPRO     := chordpro
PROJECT_CFG  := chordpro-ukulele.json
SONGBOOKS    := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard songbooks/*/*.cho)))))
PDF_DIR      := pdf
PDFS         := $(foreach sb,$(SONGBOOKS),$(PDF_DIR)/$(sb).pdf)
GS           := gs
PYTHON       := python3
MAKE_COVER   := $(PYTHON) scripts/make-cover.py

.PHONY: all clean $(SONGBOOKS)

all: $(SONGBOOKS)

$(PDF_DIR):
	mkdir -p $(PDF_DIR)

# Check if a songbook has cover pages (00-cover.cho, 01-chord-chart.cho, 99-back-cover.cho)
COVER_FILES = 00-cover.cho 01-chord-chart.cho 99-back-cover.cho
COVER_EXISTS = $(wildcard $(1)/$(2))

# Cover layout inputs: images plus the optional cover.json overlay
COVER_ASSETS = $(wildcard $(1)/cover-*.png $(1)/cover-*.jpeg $(1)/back-*.png \
  $(1)/chords.png $(1)/strip-*.png $(1)/cover.json)

# Target per songbook slug: make bricioline, make bricioline-en, etc.
# Optional per-songbook layout overlay: songbooks/<slug>/layout.json
# (merged on top of the global config; later config wins)
define SONGBOOK_RULE
$(1): $(PDF_DIR)/$(1).pdf

CFG_FLAGS_$(1) := --config $(PROJECT_CFG) \
  $$(if $$(wildcard songbooks/$(1)/layout.json),--config songbooks/$(1)/layout.json)

# A songbook gets cover pages when it ships a cover.json layout or the
# legacy 00-cover.cho marker. The chord-chart page is emitted only when
# the songbook actually provides a chords.png.
HAS_COVER_$(1)  := $$(wildcard songbooks/$(1)/cover.json songbooks/$(1)/00-cover.cho)
HAS_CHART_$(1)  := $$(wildcard songbooks/$(1)/chords.png)

ifeq ($$(strip $$(HAS_COVER_$(1))),)
# No cover — render everything normally
$(PDF_DIR)/$(1).pdf: songbooks/$(1)/*.cho $(PROJECT_CFG) $$(wildcard songbooks/$(1)/layout.json) | $(PDF_DIR)
	$(CHORDPRO) $$(CFG_FLAGS_$(1)) $$(filter %.cho,$$^) -o $$@
else
# Has cover pages — generate with Python (centered), songs with ChordPro
SONG_SRCS_$(1)  := $$(wildcard songbooks/$(1)/*.cho)
SONG_ONLY_$(1)  := $$(filter-out $$(addprefix songbooks/$(1)/,$(COVER_FILES)),$$(SONG_SRCS_$(1)))

COVER_PDF_$(1)  := $(PDF_DIR)/$(1)-cover.pdf
BACK_PDF_$(1)   := $(PDF_DIR)/$(1)-back.pdf
CHART_PDF_$(1)  := $$(if $$(HAS_CHART_$(1)),$(PDF_DIR)/$(1)-chart.pdf)
SONGS_PDF_$(1)  := $$(if $$(SONG_ONLY_$(1)),$(PDF_DIR)/$(1)-songs.pdf)
PARTS_$(1)      := $$(COVER_PDF_$(1)) $$(CHART_PDF_$(1)) $$(SONGS_PDF_$(1)) $$(BACK_PDF_$(1))

# Generate cover (and chart, when present) and back PDFs via Python
$$(COVER_PDF_$(1)) $$(CHART_PDF_$(1)) $$(BACK_PDF_$(1)) &: scripts/make-cover.py $$(call COVER_ASSETS,songbooks/$(1)) | $(PDF_DIR)
	$(MAKE_COVER) songbooks/$(1) $(PDF_DIR)

# Songs rendered via ChordPro (2-column)
$$(SONGS_PDF_$(1)): $$(SONG_ONLY_$(1)) $(PROJECT_CFG) $$(wildcard songbooks/$(1)/layout.json) | $(PDF_DIR)
	$(CHORDPRO) $$(CFG_FLAGS_$(1)) $$(filter %.cho,$$^) -o $$@

# Final merge: cover + chord-chart + songs + back cover
$(PDF_DIR)/$(1).pdf: $$(PARTS_$(1))
	$(GS) -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -sOutputFile=$$@ $$(PARTS_$(1))
	rm -f $$(PARTS_$(1))
endif
endef

$(foreach sb,$(SONGBOOKS),$(eval $(call SONGBOOK_RULE,$(sb))))

clean:
	rm -f $(PDFS) $(PDF_DIR)/*-cover.pdf $(PDF_DIR)/*-chart.pdf \
	  $(PDF_DIR)/*-songs.pdf $(PDF_DIR)/*-back.pdf
