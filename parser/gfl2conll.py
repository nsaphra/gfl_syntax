""" Usage: python gfl2conll.py infile.anno outfile.conll """

import re
import sys
from gfl_parser import *

class NodeConll(object):
    def __init__(self, ind, tok, parent):
        self.ind = ind
        self.tok = tok
        self.lower = tok.lower()
        self.parent = parent

    def tostring(self):
        return "\t".join([str(self.ind), self.tok, self.lower,
                    "_", "_", "_", str(self.parent), "_", "_", "_"])

class ConverterGfl2Conll:
    def __init__(self, gfl_parse, sentence):
        self.sent = sentence.split()
        self.gfl = goparse(self.sent, gfl_parse)
        self.node_evals = {}
        self.conll = [NodeConll(1, "ROOT", 0)]
        self.node_equivs = {}

    def __get_original_token(self, tok):
        """ Returns the original form of a duplicate token
        with format tok_1 or same token for non-dupe """
        # TODO pick a less channel-mixing strategy for
        # handling dupes
        m = re.match(r'^(.*)_(\d+)$', tok)
        if (m):
            return m.group(1)
        return tok

    def __evaluate_nodes(self):
        """ Form a dictionary in which each variable node
        points through a series of edges to the node
        which its children should point to in CoNLL """
        cbb_edges = {}
        for (head, child, label) in self.gfl.node_edges:
            if label == "Anaph":
                continue
            if label == "unspec":
                # part of a CBB constituent
                cbb_edges[child] = head
                continue
            assert child not in self.node_evals
            self.node_evals[child] = head

        # handle CBB edges saved
        for (child, head) in cbb_edges.items():
            if child not in self.node_evals:
                self.node_evals[child] = head

        for (n, ws) in self.gfl.extra_node2words.items():
            # replace variable head with first coordinate
            # eg., "$x :: a :: {p q}" gives "$x":"p"
            small = 500
            for w in ws:
                if w in self.sent:
                    small = min([small, self.sent.index(w)])
            if small == 500:
                continue
            head = self.sent[small]

            assert n not in self.node_equivs
            self.node_equivs[n] = head
            for w in ws:
                if w[0] != self.node_equivs[n]:
                    self.node_evals[w[0]] = n
        for (n, ws) in self.gfl.node2words.items():
            small = 500
            for w in ws:
                if w in self.sent:
                    small = min([small, self.sent.index(w)])
            if small == 500:
                continue
            head = self.sent[small]

            assert n not in self.node_equivs
            self.node_equivs[n] = head
            for w in ws:
                if w != self.node_equivs[n]:
                    self.node_evals[w] = n

        # finally, ensure that all leaf nodes in equiv point to parent
        for (n, w) in self.node_equivs.items():
            if n in self.node_evals:
                self.node_evals[w] = self.node_evals[n]

    def __get_ancestor(self, tok):
        """ Return the most recent ancestor associated with a leaf token """
        curr = tok
        while curr in self.node_evals:
            if (curr in self.node_equivs and self.node_equivs[curr] != tok):
                break
            curr = self.node_evals[curr]

        if (curr in self.node_equivs and self.node_equivs[curr] != tok):
            return self.sent.index(self.node_equivs[curr]) + 2
        return 1

    def convert2conll(self):
        """ Convert a GFL statement to CONLL """
        if not len(self.node_evals):
            self.__evaluate_nodes()
        ret = self.conll[0].tostring()

        for (i, tok) in enumerate(self.sent):
            orig = self.__get_original_token(tok)
            parent = self.__get_ancestor(tok)
            self.conll.append(NodeConll(i+2, orig, parent))
            ret = ret + "\n" + self.conll[i+1].tostring()

        return ret

if __name__ == "__main__":
    infile = open(sys.argv[1], 'r')
    outfile = open(sys.argv[2], 'w')

    section = ""
    text = ""
    anno = ""
    for line in infile:
        if line.startswith("%"):
            section = line.strip()
            continue
        if line.strip() == "---":
            if not anno.strip() or not text.strip():
                continue
            t = ConverterGfl2Conll(anno, text)
            outfile.write(t.convert2conll())
            outfile.write("\n")
            anno = ""
            text = ""
        elif section == "% ANNO":
            anno += line
        elif section == "% TEXT":
            text += line

    if anno.strip() and text.strip():
        t = ConverterGfl2Conll(anno, text)
        outfile.write(t.convert2conll())
    infile.close()
    outfile.close()

def test_simple():
    # 1 a a 0
    # 2 b b 1
    # 3 c c 4
    # 4 d d 2
    t = ConverterGfl2Conll("a < b < (c > d)", "a b c d")
    return t.convert2conll()

def test_brackets():
    # 1 ROOT root 0
    # 2 a a 2
    # 3 b b 0
    # 4 c c 2
    # 5 d d 3
    t = ConverterGfl2Conll("a > b < [c d]", "a b c d")
    return t.convert2conll()

def test_coord():
    # 1 ROOT root 0
    # 2 a a 4
    # 3 b b 4
    # 4 c c 1
    t = ConverterGfl2Conll("$x :: {a b} :: c", "a b c")
    return t.convert2conll()

def test_coord_2():
    # 1 ROOT root 0
    # 2 a a 3
    # 3 b b 3
    # 4 c c 0
    # 5 d d 3
    t = ConverterGfl2Conll("$x :: {a b} :: {c d}", "a b c d")
    return t.convert2conll()

def test_dupes():
    # 1 ROOT root 0
    # 2 a a 0
    # 3 b b 1
    # 4 c c 4
    # 5 a a 2
    t = ConverterGfl2Conll("a_1 < b < (c > a_2)", "a_1 b c a_2")
    return t.convert2conll()
