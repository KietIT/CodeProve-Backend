from difflib import SequenceMatcher


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def cluster_near_duplicates(texts: list[str], threshold: float, min_cluster: int = 3) -> int:
    used = [False] * len(texts)
    clusters = 0
    for i in range(len(texts)):
        if used[i]:
            continue
        group = [i]
        for j in range(i + 1, len(texts)):
            if not used[j] and similar(texts[i], texts[j]) >= threshold:
                group.append(j)
        if len(group) >= min_cluster:
            clusters += 1
            for k in group:
                used[k] = True
    return clusters
