#!/usr/bin/env python

from __future__ import print_function


def rangify(integers):
    if integers:
        pred = []
        for i in sorted(map(int, integers)):
            if pred and 1 + pred[1] == i:
                pred[1] = i
            else:
                if pred:
                    yield pred
                pred = [i, i]
        yield pred


def squoosh_range(r):
    if r[0] == r[1]:
        return [r[0]]
    else:
        return r


if __name__ == "__main__":
    import fileinput

    for range in rangify(fileinput.input()):
        print("-".join(map(str, squoosh_range(range))))
