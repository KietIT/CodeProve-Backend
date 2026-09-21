import pytest

pytestmark = pytest.mark.asyncio

TWO_SUM = (
    "def two_sum(nums, target):\n"
    "    seen = {}\n"
    "    for i in range(len(nums)):\n"
    "        complement = target - nums[i]\n"
    "        if complement in seen:\n"
    "            return [seen[complement], i]\n"
    "        seen[nums[i]] = i\n"
)


async def test_trace_returns_per_line_frames_with_array_pointer(client):
    r = await client.post(
        "/api/practice/trace",
        json={"source_code": TWO_SUM, "call": "two_sum([2, 7, 11, 15], 9)"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    assert len(body["frames"]) > 3
    # Some frame shows nums as an array with a pointer (i) into it.
    ptr_frames = [
        f for f in body["frames"]
        if f["locals"].get("nums", {}).get("kind") == "array" and f["locals"]["nums"].get("ptrs")
    ]
    assert ptr_frames, "expected an array frame with a pointer"
    assert "i" in ptr_frames[0]["locals"]["nums"]["ptrs"]


async def test_trace_renders_dict_as_map(client):
    src = "def count(xs):\n    d = {}\n    for x in xs:\n        d[x] = d.get(x, 0) + 1\n    return d\n"
    r = await client.post("/api/practice/trace", json={"source_code": src, "call": "count(['a','b','a'])"})
    assert r.status_code == 200
    frames = r.json()["frames"]
    maps = [f["locals"]["d"] for f in frames if f["locals"].get("d", {}).get("kind") == "map"]
    assert maps and maps[-1]["entries"]  # dict captured as a map


async def test_trace_of_empty_body_has_no_array_frames(client):
    r = await client.post("/api/practice/trace", json={"source_code": "def f(nums):\n    pass\n", "call": "f([1,2,3])"})
    assert r.status_code == 200
    frames = r.json()["frames"]
    # `pass` produces at most one trivial frame and no populated array to animate.
    assert not any(f["locals"].get("nums", {}).get("ptrs") for f in frames)
