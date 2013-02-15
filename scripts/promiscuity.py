import re
import sys
import json
import copy

top_node = "$$"

class TreeNode(object):
    def __init__(self, name, children):
        self.name = name
        self.children = set(children)

    def add_child(self, child):
        self.children.add(child)

    def remove_child(self, child):
        self.children.remove(child)

    def deepcopy(self):
        return TreeNode(self.name,
                        [child.deepcopy() for child in self.children])            

class PromiscuityMeasure(object):
    def __init__(self, json_line):
        anno = json.loads(json_line)
        self.node2words = anno['node2words']
        self.tokens = anno['tokens']
        self.node_edges = anno['node_edges']
        self.nodes = anno['nodes']
        self.extra_node2words = anno['extra_node2words']
        self.cbb_edges = {}
        self.cbb_edges_inv = {}
        self.cbb_heads = {}
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

        # restrict parents of non-head CBB components within the CBB
        for (head, children) in self.cbb_edges.items():
            for child in children:
                if child not in self.cbb_heads[head]:
                    self.graph[child] = self.graph[child].intersection(self.cbb_edges[head])

        for (head, child, label) in self.node_edges:
            if label == "Anaph" or label == "unspec":
                continue

            if head in self.cbb_heads and child in self.graph:
                # if arc attaches w to CBB, remove all outgoing edges
                # outside of CBB
                self.graph[child] = set(self.cbb_heads[head])
                continue

            elif child in self.cbb_edges:
                # if CBB has an outgoing edge, all components of CBB
                # must have either a head in that CBB
                # or the outgoing edge head
                potential_heads = set(self.cbb_edges[child])
                if head in self.graph:
                    potential_heads.add(head)
                elif head in self.cbb_edges:
                    potential_heads = potential_heads.union(self.cbb_heads[head])
                else:
                    continue

                for n in self.cbb_edges[child]:
                    if n not in self.cbb_heads[child]:
                        self.graph[n] = set(self.cbb_edges[child])
                        continue
                    self.graph[n] = self.graph[n].intersection(potential_heads)

    def __invert_cbb_edges(self):
        """ fill an inverted version of self.cbb_edges, with CBB nodes as
        values and components as keys """

        for (cbb, components) in self.cbb_edges.items():
            for c in components:
                if c not in self.cbb_edges_inv:
                    self.cbb_edges_inv[c] = set()
                self.cbb_edges_inv[c].add(cbb)

    def __invert_graph(self):
        """ fill an inverted version of self.graph, with parents
        as keys and children as values """

        for (child, heads) in self.graph.items():
            for head in heads:
                self.graph_inv[head].add(child)

    def __try_specify_cbb_head(self, head, cbbs, cbb_heads):
        """ Attempt to specify one cbb head or return empty if
        head is not a valid head for cbb """

        for cbb in cbbs:
            if head not in cbb_heads[cbb]:
                return {}
            cbb_heads[cbb] = set([head])
        return cbb_heads

    def __constrain_cbbs(self, head, child, cbb_heads):
        if head in self.cbb_edges_inv:
            head_cbbs = self.cbb_edges_inv[head]
            if child in self.cbb_edges_inv:
                child_cbbs = self.cbb_edges_inv[child]

                if head_cbbs == child_cbbs:
                    # CASE 1: [cbb node] parents [node in same cbb]
                    for cbb in head_cbbs:
                        if child in cbb_heads[cbb]:
                            cbb_heads[cbb].remove(child)
                            if not cbb_heads[cbb]:
                                return {}
                    return cbb_heads

                # CASE 2: [cbb node] parents [node in different cbb]
                for cbb in child_cbbs:
                    if cbb in head_cbbs:
                        # parent gets to be head of this
                        continue
                    if child not in cbb_heads[cbb]:
                        return {}
                    cbb_heads[cbb] = set([child])
                # return below
            
            # CASE 3: [cbb node] parents [node not in cbb]
            return self.__try_specify_cbb_head(head, head_cbbs, cbb_heads)

        if child in self.cbb_edges_inv:
            # CASE 4: [node not in cbb] parents [cbb node]
            return self.__try_specify_cbb_head(child,
                                               self.cbb_edges_inv[child],
                                               cbb_heads)

        # CASE 5: both nodes not in cbb
        return cbb_heads

    def __find_trees(self, root, nodelist, cbb_heads, next_edges, ind_depth):
        """ Identify the spanning trees that meet out constraints """
        self.__print_tree(root, ind_depth)

        if len(nodelist) == len(self.graph) + 1:
            # extra node in nodelist for top_node
            self.trees.append(copy.deepcopy(root))
            return

        for (head, children) in next_edges.items():
            for child in children:
                assert child not in nodelist

                tmp_cbb_heads = self.__constrain_cbbs(head, child,
                                                      copy.deepcopy(cbb_heads))
                if not tmp_cbb_heads:
                    continue

                childnode = TreeNode(child, [])
                nodelist[head].add_child(childnode)
                nodelist[child] = childnode

                # insert new possible edges out of tree
                next_edges[child] = copy.deepcopy(self.graph_inv[child])
                # avoid adding backedges
                for c in self.graph_inv[child]:
                    if c in next_edges:
                        next_edges[child].remove(c)

                # remove newly cyclic edges
                saved_edges = set()
                for cycle_head in self.graph[child]:
                    if cycle_head not in next_edges:
                        continue
                    next_edges[cycle_head].remove(child)
                    saved_edges.add(cycle_head)

                self.__find_trees(root, nodelist, tmp_cbb_heads,
                                  next_edges, ind_depth+1)

                # add back in old cyclic edges
                for edge_head in saved_edges:
                    next_edges[edge_head].add(child)

                # remove old possible edges out of tree
                del next_edges[child]

                del nodelist[child]
                nodelist[head].remove_child(childnode)

    def promiscuity(self):
        """ Build all compatible trees and count them """

        self.__initialize_graph()
        self.__build_cbb_info()
        self.__remove_multiparents()
        self.__invert_graph()
        self.__invert_cbb_edges()

        top_root = TreeNode(top_node, [])
        self.__find_trees(top_root, {top_node: top_root},
                          copy.deepcopy(self.cbb_heads),
                          {top_node: self.graph_inv[top_node]},
                          0)
        return len(self.trees)

    def __print_tree(self, root, indent_level):
        print ("  " * indent_level) + root.name
        for child in root.children:
            self.__print_tree(child, indent_level + 1)

    def print_trees(self):
        for tree in self.trees:
            self.__print_tree(tree, 0)


if __name__ == "__main__":
    infile = open(sys.argv[1], 'r')
    outfile = open(sys.argv[2], 'w')

    for line in infile:
        p = PromiscuityMeasure(line.split('\t')[2])
        outfile.write(str(p.promiscuity()) + '\n\n')
        p.print_trees()

    infile.close()
    outfile.close()
