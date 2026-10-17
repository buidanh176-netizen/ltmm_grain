def output_h(lfsr, nfsr):
    """
    Grain v1 nonlinear output filter h(x).

    Parameters:
        lfsr: LFSR state containing 80 bits.
        nfsr: NFSR state containing 80 bits.

    Returns:
        One output-filter bit (0 or 1).
    """
    x0 = lfsr[3]
    x1 = lfsr[25]
    x2 = lfsr[46]
    x3 = lfsr[64]
    x4 = nfsr[63]

    h = (
        x1 ^ x4
        ^ (x0 & x3)
        ^ (x2 & x3)
        ^ (x3 & x4)
        ^ (x0 & x1 & x2)
        ^ (x1 & x2 & x3)
        ^ (x1 & x2 & x4)
        ^ (x2 & x3 & x4)
    )

    return h & 1