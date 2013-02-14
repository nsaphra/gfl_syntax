import re
import sys
import json

top_node = "$$"

class TreeNode(object):
    def __init__(self, name, children):
        self.name = name
        self.children = set(children)

    def add_child(self, child):
        self.children.add(child)

    def remove_child(self, child):
        self.children.remove(child)

    def deep_copy(self):
        return TreeNode(self.name,
                        [child.deep_copy() for child in self.children])
            

class PromiscuityMeasure(object):
    def __init__(self, json_line):
        anno = json.loads(json_line)
        self.node2words = anno['node2words']
        self.tokens = anno['tokens']
        self.node_edges = anno['node_edges']
        self.nodes = anno['nodes']
        self.extra_node2words = anno['extra_node2words']
        self.cbb_edges = {}
        self.cbb_heads = {}
        self.cbb_incoming = {}
        self.cbb_outgoing = {}
        self.trees = []
        self.graph = {}
        self.graph_inv = {}

    def __initialize_graph(self):
        """ Initialize the complete graph connecting all
        nodes and unannotated tokens """

        node_toks = set([j 
                         for i in self.node2words.values()
                         for j in i])
        # nodes used in annotation
        graph_nodes = self.node2words.keys()
        # tokens left unannotated
        for t in self.tokens:
            if t not in node_toks:
                graph_nodes += [t]

        # initialize complete graph
        self.graph_inv[top_node] = set()
        for node1 in graph_nodes:
            self.graph[node1] = set([top_node])
            self.graph_inv[node1] = set()
            for node2 in graph_nodes:
                if node1 == node2:
                    continue
                self.graph[node1].add(node2)

    def __specified(self, l):
        """ Is edge to l fully specified? """

        return len(l) == 1

    def __build_cbb_info(self):
        """ Identify which components belong to which CBBs
        and list potential CBB heads """

        # build list of CBB components
        for (head, child, label) in self.node_edges:
            if label == "unspec":
                # part of a CBB constituent
                if head not in self.cbb_edges:
                    self.cbb_edges[head] = set()
                self.cbb_edges[head].add(child)
                continue
            if label == "Anaph":
                continue
            # build basic edges between word nodes
            if head in self.graph and child in self.graph:
                self.graph[child] = set([head])

        # build list of potential CBB heads
        for (node, children) in self.cbb_edges.items():
            self.cbb_heads[node] = set(children)
            for child in children:
                if len(self.graph[child]) == 1:
                    parent = iter(self.graph[child]).next()
                    if parent not in self.cbb_edges:
                        # TODO can child connect to a non-word
                        # node inside constituent?
                        self.cbb_heads[node] = set([child])
                        break
                    else:
                        self.cbb_heads[node].remove(child)        

    def __remove_multiparents(self):
        """ Remove extra edges if node connects to a CBB with
        known head """

        for (head, child, label) in self.node_edges:
            if label == "Anaph" or label == "unspec":
                continue
            if head in self.cbb_heads and child in self.graph:
                # if arc attaches w to CBB, remove all outgoing edges
                # outside of CBB
                self.graph[child] = set(self.cbb_heads[head])
                self.cbb_incoming[child] = head
                continue
            elif child in self.cbb_heads:
                # if CBB has an outgoing edge, all components of CBB
                # must have either a head in that CBB
                # or the outgoing edge head
                potential_heads = set()
                if head in self.graph:
                    potential_heads.add(head)
                elif head in self.cbb_edges:
                    potential_heads = self.cbb_heads[head]
                else:
                    continue
                for n in self.cbb_edges[child]:
                    self.graph[n].union(potential_heads)

    def __invert_graph(self):
        """ return an inverted version of self.graph, with parents
        as keys and children as values """

        for (child, heads) in self.graph.items():
            for head in heads:
                self.graph_inv[head].add(child)

    def __find_trees(self, root, nodelist):
        """ Identify the spanning trees that meet out constraints """

        if len(nodelist) == len(self.graph):
            self.trees.append(root.deep_copy())

        for node in nodelist:
            new_children = set()
            for child in self.graph_inv[node]:
                if child in nodelist:
                    new_children.add(child)
                    continue
                childnode = TreeNode(child, [])
                nodelist[node].add_child(childnode)
                nodelist[child] = childnode

                self.__find_trees(root, nodelist)

                del nodelist[child]
                nodelist[node].remove_child(childnode)
            self.graph_inv[node] = new_children


    def promiscuity(self):
        """ Build all compatible trees and count them """

        self.__initialize_graph()
        self.__build_cbb_info()
        self.__remove_multiparents()
        self.__invert_graph()

        top_root = TreeNode(top_node, [])
        self.__find_trees(top_root, {top_node: top_root})
        return len(self.trees)


if __name__ == "__main__":
    infile = open(sys.argv[1], 'r')
    outfile = open(sys.argv[2], 'w')

    for line in infile:
        p = PromiscuityMeasure(line.split('\t')[2])
        outfile.write(str(p.promiscuity()) + '\n\n')

    infile.close()
    outfile.close()
