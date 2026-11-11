import numpy as np
from PIL import Image, ImageFilter, ImageOps

from scripts.build_extended_dataset import fingerprints, groups


def leaf(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    a = (rng.random((96, 96, 3)) * 255).astype(np.uint8)
    return Image.fromarray(a).filter(ImageFilter.GaussianBlur(3))


def test_rotated_and_flipped_copies_share_a_group_but_different_photos_do_not():
    a, b = leaf(1), leaf(2)
    photos = [a, a.rotate(90, expand=True), ImageOps.mirror(a), a.rotate(180).resize((120, 120)), b, ImageOps.flip(b)]
    g = groups(np.stack([fingerprints(p) for p in photos]))
    assert len({g[0], g[1], g[2], g[3]}) == 1          # all copies of photo a together
    assert g[4] == g[5] and g[4] != g[0]               # photo b is its own group


def test_splits_are_balanced_even_with_one_huge_group():
    import random

    from scripts.build_extended_dataset import assign_splits

    sizes = [400] + [1] * 600
    splits = assign_splits(sizes, random.Random(0))
    count = {s: sum(n for n, sp in zip(sizes, splits) if sp == s) for s in ("train", "val", "test")}
    assert splits[0] == "train" and count["val"] > 100 and count["test"] > 100
