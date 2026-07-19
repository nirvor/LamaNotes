const defaultSuggestionLimit = 6;

function normalizeSearchText(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase()
    .replace(/[#_-]+/g, " ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function tokenize(value) {
  const normalized = normalizeSearchText(value);
  return normalized ? normalized.split(" ") : [];
}

function allTokensMatchPrefixes(queryTokens, fieldTokens) {
  return queryTokens.every((queryToken) =>
    fieldTokens.some((fieldToken) => fieldToken.startsWith(queryToken)),
  );
}

function allTokensOccur(queryTokens, normalizedField) {
  return queryTokens.every((queryToken) =>
    normalizedField.includes(queryToken),
  );
}

function titleMatchScore(title, query, queryTokens) {
  const normalizedTitle = normalizeSearchText(title);
  if (!normalizedTitle) {
    return 0;
  }
  if (normalizedTitle === query) {
    return 1200;
  }
  if (normalizedTitle.startsWith(query)) {
    return 1120;
  }
  if (normalizedTitle.includes(query)) {
    return 1040;
  }

  const titleTokens = tokenize(normalizedTitle);
  if (allTokensMatchPrefixes(queryTokens, titleTokens)) {
    return 980;
  }
  if (allTokensOccur(queryTokens, normalizedTitle)) {
    return 920;
  }
  if (
    queryTokens.length === 1 &&
    queryTokens.some((queryToken) =>
      titleTokens.some((titleToken) => titleToken.startsWith(queryToken)),
    )
  ) {
    return 760;
  }
  return 0;
}

function metadataMatchScore(note, query, queryTokens) {
  const normalizedTags = (Array.isArray(note.tags) ? note.tags : [])
    .map(normalizeSearchText)
    .filter(Boolean);
  if (normalizedTags.some((tag) => tag === query)) {
    return 620;
  }
  if (allTokensMatchPrefixes(queryTokens, normalizedTags)) {
    return 560;
  }

  const normalizedSummary = normalizeSearchText(note.summary);
  if (normalizedSummary.includes(query)) {
    return 480;
  }
  if (normalizedSummary && allTokensOccur(queryTokens, normalizedSummary)) {
    return 430;
  }

  const combinedMetadata = `${normalizedTags.join(" ")} ${normalizedSummary}`;
  return combinedMetadata.trim() &&
    allTokensOccur(queryTokens, combinedMetadata)
    ? 380
    : 0;
}

export function getSearchSuggestions(
  index,
  rawQuery,
  limit = defaultSuggestionLimit,
) {
  const query = normalizeSearchText(rawQuery);
  const queryTokens = tokenize(query);
  const suggestionLimit = Math.max(0, Number(limit) || 0);
  if (!query || queryTokens.length === 0 || suggestionLimit === 0) {
    return [];
  }

  return (Array.isArray(index) ? index : [])
    .map((note) => {
      const titleScore = titleMatchScore(note.title, query, queryTokens);
      const metadataScore = metadataMatchScore(note, query, queryTokens);
      const score = Math.max(titleScore, metadataScore);
      return {
        ...note,
        matchKind: titleScore > 0 ? "title" : "metadata",
        suggestionScore: score,
      };
    })
    .filter((note) => note.suggestionScore > 0)
    .sort((left, right) => {
      if (right.suggestionScore !== left.suggestionScore) {
        return right.suggestionScore - left.suggestionScore;
      }
      const modifiedDifference =
        Number(right.last_modified || 0) - Number(left.last_modified || 0);
      if (modifiedDifference !== 0) {
        return modifiedDifference;
      }
      return String(left.title || "").localeCompare(String(right.title || ""));
    })
    .slice(0, suggestionLimit);
}
