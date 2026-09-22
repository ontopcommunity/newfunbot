#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vietnamese word-link dictionary helper."""
from __future__ import annotations

import os
import random
from collections import defaultdict
from typing import Dict, List, Optional, Set

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICT = os.path.join(_HERE, "filtered_words.txt")


class WordDict:
    def __init__(self, path: str = DEFAULT_DICT):
        self.words: List[str] = []
        self.by_first: Dict[str, List[str]] = defaultdict(list)
        self._load(path)

    def _load(self, path: str) -> None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Dictionary not found: {path}")
        seen: Set[str] = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                w = line.strip().lower()
                if not w or " " not in w:
                    continue
                if w in seen:
                    continue
                seen.add(w)
                self.words.append(w)
                first = w.split()[0]
                self.by_first[first].append(w)
        # shuffle each bucket so we don't always pick the same answer
        for k in self.by_first:
            random.shuffle(self.by_first[k])

    def next_words(self, last_syllable: str, used: Set[str], limit: int = 20) -> List[str]:
        key = last_syllable.lower().strip()
        cands = [w for w in self.by_first.get(key, []) if w not in used]
        return cands[:limit]

    def pick(self, last_syllable: str, used: Set[str]) -> Optional[str]:
        cands = self.next_words(last_syllable, used, limit=30)
        if not cands:
            return None
        return cands[0]
