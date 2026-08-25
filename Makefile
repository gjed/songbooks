CHORDPRO     := chordpro
PROJECT_CFG  := chordpro-ukulele.json
SONGBOOKS    := $(sort $(notdir $(patsubst %/,%,$(dir $(wildcard songbooks/*/*.cho)))))
PDF_DIR      := pdf
HTML_DIR     := html
PDFS         := $(foreach sb,$(SONGBOOKS),$(PDF_DIR)/$(sb).pdf)
GS           := gs
PYTHON       := python3
HUGO         ?= hugo
MAKE_COVER   := $(PYTHON) scripts/make-cover.py
# Cover generation sources: the entry point plus the shared metadata reader
# it imports, so a change to either rebuilds every cover page.
COVER_SCRIPTS := scripts/make-cover.py scripts/songbook_meta.py
SPOTIFY      := $(PYTHON) scripts/spotify_playlists.py
SITE_DATA    := $(PYTHON) scripts/site-data.py

.PHONY: all clean html $(SONGBOOKS)

all: $(SONGBOOKS)

$(PDF_DIR):
	mkdir -p $(PDF_DIR)

# Check if a songbook has cover pages (00-cover.cho, 01-chord-chart.cho, 99-back-cover.cho)
COVER_FILES = 00-cover.cho 01-chord-chart.cho 99-back-cover.cho
COVER_EXISTS = $(wildcard $(1)/$(2))

# Cover layout inputs: images plus the songbook.yaml layout sections
COVER_ASSETS = $(wildcard $(1)/cover-*.png $(1)/cover-*.jpeg $(1)/back-*.png \
  $(1)/chords.png $(1)/strip-*.png $(1)/songbook.yaml)

# Target per songbook slug: make bricioline, make bricioline-en, etc.
# Optional per-songbook layout overlay: songbooks/<slug>/layout.json
# (merged on top of the global config; later config wins)
define SONGBOOK_RULE
$(1): $(PDF_DIR)/$(1).pdf

CFG_FLAGS_$(1) := --config $(PROJECT_CFG) \
  $$(if $$(wildcard songbooks/$(1)/layout.json),--config songbooks/$(1)/layout.json)

# A songbook gets cover pages only when its songbook.yaml declares a
# `cover:` section — every songbook ships a songbook.yaml, so mere file
# existence gates nothing. The chord-chart page is emitted only when the
# songbook actually provides a chords.png.
HAS_COVER_$(1)  := $$(shell grep -ls '^cover:' songbooks/$(1)/songbook.yaml 2>/dev/null)
HAS_CHART_$(1)  := $$(wildcard songbooks/$(1)/chords.png)
# The intro page (album description + Spotify link) exists only when the
# songbook.yaml declares an `intro:` section.
HAS_INTRO_$(1)  := $$(shell grep -ls '^intro:' songbooks/$(1)/songbook.yaml 2>/dev/null)

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
INTRO_PDF_$(1)  := $$(if $$(HAS_INTRO_$(1)),$(PDF_DIR)/$(1)-intro.pdf)
SONGS_PDF_$(1)  := $$(if $$(SONG_ONLY_$(1)),$(PDF_DIR)/$(1)-songs.pdf)
PARTS_$(1)      := $$(COVER_PDF_$(1)) $$(INTRO_PDF_$(1)) $$(CHART_PDF_$(1)) $$(SONGS_PDF_$(1)) $$(BACK_PDF_$(1))

# Generate cover (and intro/chart, when present) and back PDFs via Python
$$(COVER_PDF_$(1)) $$(INTRO_PDF_$(1)) $$(CHART_PDF_$(1)) $$(BACK_PDF_$(1)) &: $(COVER_SCRIPTS) $$(call COVER_ASSETS,songbooks/$(1)) | $(PDF_DIR)
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

# HTML render for the online read view: one file per song, so editing one
# .cho re-renders only that song. ChordPro would happily aggregate a whole
# songbook into a single document, but the site links to songs individually.
# Cover pseudo-songs are excluded — they are drawn by reportlab for print and
# have no HTML equivalent.
define HTML_RULE
HTML_SRCS_$(1) := $$(filter-out $$(addprefix songbooks/$(1)/,$(COVER_FILES)),$$(wildcard songbooks/$(1)/*.cho))
HTML_OUT_$(1)  := $$(patsubst songbooks/$(1)/%.cho,$(HTML_DIR)/$(1)/%.html,$$(HTML_SRCS_$(1)))
HTML_TARGETS   += $$(HTML_OUT_$(1))

$(HTML_DIR)/$(1)/%.html: songbooks/$(1)/%.cho $(PROJECT_CFG) $$(wildcard songbooks/$(1)/layout.json)
	@mkdir -p $$(dir $$@)
	$(CHORDPRO) $$(CFG_FLAGS_$(1)) --generate=HTML $$< -o $$@
endef

$(foreach sb,$(SONGBOOKS),$(eval $(call HTML_RULE,$(sb))))

html: $(HTML_TARGETS)

# Ad-hoc preview: render a full songbook (cover, chord chart, back cover,
# songs) exactly like `make <slug>`, but for guitar instead of ukulele.
# Swaps in the guitar instrument (tuning + chord diagrams) on top of the
# project config; cover/back/chart pages are unaffected by instrument.
# Usage: make guitar-ita SB=<songbook-slug>   (Italian chord notation)
#        make guitar-eng SB=<songbook-slug>   (English chord notation)
.PHONY: guitar-ita guitar-eng
guitar-ita guitar-eng: | $(PDF_DIR)
	@test -n "$(SB)" || { echo "Usage: make $@ SB=<songbook-slug>"; exit 1; }
	@test -d songbooks/$(SB) || { echo "No such songbook: songbooks/$(SB)"; exit 1; }
	$(CHORDPRO) --config $(PROJECT_CFG) --config guitar \
	  $(if $(wildcard songbooks/$(SB)/layout.json),--config songbooks/$(SB)/layout.json) \
	  --transcode=$(if $(filter guitar-ita,$@),latin,common) \
	  $(filter-out songbooks/$(SB)/00-cover.cho songbooks/$(SB)/01-chord-chart.cho songbooks/$(SB)/99-back-cover.cho,$(wildcard songbooks/$(SB)/*.cho)) \
	  -o $(PDF_DIR)/$(SB)-$@-songs.pdf
	@if grep -qs '^cover:' songbooks/$(SB)/songbook.yaml; then \
	  $(MAKE_COVER) songbooks/$(SB) $(PDF_DIR) ; \
	  parts="$(PDF_DIR)/$(SB)-cover.pdf" ; \
	  [ -f $(PDF_DIR)/$(SB)-intro.pdf ] && parts="$$parts $(PDF_DIR)/$(SB)-intro.pdf" ; \
	  [ -f $(PDF_DIR)/$(SB)-chart.pdf ] && parts="$$parts $(PDF_DIR)/$(SB)-chart.pdf" ; \
	  parts="$$parts $(PDF_DIR)/$(SB)-$@-songs.pdf $(PDF_DIR)/$(SB)-back.pdf" ; \
	  $(GS) -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -sOutputFile=$(PDF_DIR)/$(SB)-$@.pdf $$parts ; \
	  rm -f $(PDF_DIR)/$(SB)-cover.pdf $(PDF_DIR)/$(SB)-intro.pdf $(PDF_DIR)/$(SB)-chart.pdf $(PDF_DIR)/$(SB)-back.pdf $(PDF_DIR)/$(SB)-$@-songs.pdf ; \
	else \
	  mv $(PDF_DIR)/$(SB)-$@-songs.pdf $(PDF_DIR)/$(SB)-$@.pdf ; \
	fi

clean:
	rm -f $(PDFS) $(PDF_DIR)/*-cover.pdf $(PDF_DIR)/*-intro.pdf \
	  $(PDF_DIR)/*-chart.pdf $(PDF_DIR)/*-songs.pdf $(PDF_DIR)/*-back.pdf \
	  $(PDF_DIR)/*-guitar-ita.pdf $(PDF_DIR)/*-guitar-eng.pdf
	rm -rf $(HTML_DIR)

# Spotify playlist sync: two-phase model
# - resolve: interactive local curation, writes committed songbooks/<slug>/spotify.yaml
# - sync: pushes already-pinned track URIs, never searches (dry-run by default)
.PHONY: spotify-validate spotify-resolve spotify-sync spotify-sync-apply

spotify-validate:
	$(SPOTIFY) validate

spotify-resolve:
	$(SPOTIFY) resolve $(if $(SB),--songbook $(SB))

spotify-sync:
	$(SPOTIFY) sync $(if $(SB),--songbook $(SB))

spotify-sync-apply:
	$(SPOTIFY) sync --apply $(if $(SB),--songbook $(SB))

# Hugo site generation
.PHONY: site site-serve

site: all html
	$(SITE_DATA)
	$(HUGO) --source site --minify

site-serve: all html
	$(SITE_DATA)
	$(HUGO) server --source site
