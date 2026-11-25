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

$(B)/units.json: $(SRC)
	$(STAGE_CMD) units $(CHAPTER)
$(B)/nodes.json $(B)/coverage.md: $(B)/units.json $(PACK)
	$(STAGE_CMD) nodes $(CHAPTER)
$(B)/routing.json: $(B)/nodes.json
	$(STAGE_CMD) routing $(CHAPTER)
$(B)/verify.md: $(B)/nodes.json $(B)/coverage.md $(B)/routing.json
	$(STAGE_CMD) verify $(CHAPTER)
out/$(CHAPTER)/index.html: $(B)/verify.md $(B)/routing.json
	$(STAGE_CMD) course $(CHAPTER)
