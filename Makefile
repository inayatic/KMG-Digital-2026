# make course CHAPTER=latyshova   — полный прогон; правка входа пересобирает только зависимое
# STAGE_CMD можно подменить (например, на `echo` для сухого прогона).
CHAPTER ?=
STAGE_CMD ?= python3 tools/stage.py
B = build/$(CHAPTER)
SRC = $(wildcard chapters/$(CHAPTER)/*)
PACK = $(wildcard domain-pack/*) $(wildcard schema/*.json)

.PHONY: course check
check:
	@test -n "$(CHAPTER)" || (echo "usage: make course CHAPTER=<name>"; exit 2)

course: check out/$(CHAPTER)/index.html

$(B)/clean.md $(B)/clean-report.json: $(SRC) tools/clean_ref.py
	python3 -I tools/clean_ref.py $(CHAPTER)
$(B)/units.json: $(B)/clean.md tools/make_units.py
	python3 -I tools/make_units.py $(CHAPTER)
$(B)/nodes.json $(B)/coverage.md: $(B)/units.json $(PACK)
	$(STAGE_CMD) nodes $(CHAPTER)
$(B)/verify.md: $(B)/nodes.json $(B)/coverage.md
	$(STAGE_CMD) verify $(CHAPTER)
$(B)/org/layer.json: $(B)/verify.md
	$(STAGE_CMD) org $(CHAPTER)
out/$(CHAPTER)/index.html: $(B)/org/layer.json
	$(STAGE_CMD) course $(CHAPTER)

# Слой в формате организаторов (после стадии nodes/enrich): make org CHAPTER=latyshova
.PHONY: org
org: check
	python3 -I tools/merge_layer.py $(CHAPTER)
	python3 -I tools/to_organizer_schema.py $(CHAPTER)
	python3 -I tools/apply_patches.py $(CHAPTER)
	python3 -I tools/check_org.py $(CHAPTER)
