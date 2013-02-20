class ConstrainedFUDG(FUDGGraph):
    def __find_cbb_heads(self):
        upward(self)
        downward(self)

    def __constrain_cbbs(self):
        raise NotImplementedException

    def spanning(self):
        
