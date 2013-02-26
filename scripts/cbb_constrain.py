from graph import FUDGGraph, CBBNode

def constrain_cbbs(trees, fudg):
    """
    Returns only the trees that adhere to constraint that there can
    only be a single head in each CBB.

    trees: potential dependency trees over fudg
    fudg: fudggraph for a document
    """
    constrained = []

    # build dict of cbb -> components
    cbb_children = {}
    for cbb in fudg.cbbnodes:
        cbb_children[cbb.name] = cbb.members

    def get_cbbs_containing(n):
        cbbs = set()
        for (cbb, children) in cbb_children:
            if n in children:
                cbbs.add(cbb)
        return cbbs

    def constrain(head, child, cbbs):
        t_ok = True

        for cbb in cbbs:
            if head not in cbb:
                if cbb in cbb_tops:
                    if cbb_tops[cbb] != child:
                        t_ok = False
                        break
                else:
                    cbb_tops[cbb] = child
        return t_ok

    for t in trees:
        t_ok = True
        cbb_tops = {}
        for (head, child) in t:
            if not t_ok:
                break

            head_cbbs = get_cbbs_containing(head)
            child_cbbs = get_cbbs_containing(child)
            t_ok = constrain(head, child, head_cbbs) and\
                constrain(head, child, child_cbbs)
        if t_ok:
            constrained.append(t)
    return constrained
