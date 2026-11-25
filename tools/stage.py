#!/usr/bin/env python3
"""Диспетчер стадий: stage.py <units|nodes|routing|verify|course> <chapter>.
Каждая стадия = субагент из .claude/agents. Пока стадии не реализованы: падаем явно, не создаём пустых файлов."""
import sys
AGENT = {"units": "layer-extractor", "nodes": "layer-extractor", "routing": "layer-extractor",
         "verify": "verifier", "course": "course-builder"}
stage, chapter = sys.argv[1:3]
sys.exit(f"stage '{stage}' ({AGENT[stage]}) for '{chapter}': not implemented yet")
