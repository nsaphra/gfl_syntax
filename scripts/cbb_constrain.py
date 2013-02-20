from graph import FUDGGraph

def constrain_cbbs(trees, fudg):
    constrained = []

    cbb_children = {}
    for (cbb, child) in fudg.cbbnodes:
        if cbb not in cbb_children:
            cbb_children[cbb] = set()
            cbb_children[cbb].add(child)


    def get_cbbs_containing(n):
        cbbs = set()
        for (cbb, children) in cbb_children:
            if n in children:
                cbbs.add(cbb)
        return cbbs


    for t in trees:
        t_ok = True
        cbb_tops = {}
        for (head, child) in t:
            if not t_ok:
                break

            cbbs = get_cbbs_containing(child)
            for cbb in cbbs:
                if head not in cbb:
                    if cbb in cbb_tops:
                        if cbb_tops[cbb] != child:
                            t_ok = False
                            break
                    else:
                        cbb_tops[cbb] = child
        if t_ok:
            constrained.append(t)
    return constrained
