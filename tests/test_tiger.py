from direct_connect.vendored.tiger import tiger


def round_helper(
    a: int,
    b: int,
    c: int,
    x: int,
    mul: int,
    new_a: int,
    new_b: int,
    new_c: int,
) -> None:
    ret_values = tiger.tiger_round(a, b, c, x, mul)

    assert ret_values["a"] == new_a, (
        "a failed: " + str(ret_values["a"]) + " != " + str(new_a) + "\n"
    )
    assert ret_values["c"] == new_c, (
        "c failed: " + str(ret_values["c"]) + " != " + str(new_c) + "\n"
    )
    assert ret_values["b"] == new_b, (
        "b failed: " + str(ret_values["b"]) + " != " + str(new_b) + "\n"
    )


def test_tiger_round() -> None:
    round_helper(
        13065445776871430898,
        17855811585246249540,
        518233413090174763,
        12311797252403697916,
        7,
        4821272432160810520,
        17424479681440429243,
        12532788606137106391,
    )


def test_tiger_round2() -> None:
    round_helper(
        6280199717849618378,
        8343645101657805456,
        5997044206234503415,
        12062177936022666431,
        9,
        11604645957211426640,
        3986339792283275959,
        17608143266212181064,
    )


def test_tiger_round3() -> None:
    round_helper(
        11604645957211426640,
        3986339792283275959,
        17608143266212181064,
        11490956213547313652,
        9,
        6441804261801137295,
        13333871996800360137,
        7720474646982516156,
    )


"""
Results from reference:
A: 6280199717849618378
B: 8343645101657805456
C: 5997044206234503415
mul: 9
x0: 12062177936022666431
x1: 11490956213547313652
x2: 16829172008830410301
x3: 11899344311637024046
x4: 3757253942274655973
x5: 17835857420906997132
x6: 10787740079658512390
x7: 17590610739856314589
new A: 1509595445172618351
new B: 206383248218352883
new C: 2725617220977123037

"""


def test_tiger_pass() -> None:
    a = 6280199717849618378
    b = 8343645101657805456
    c = 5997044206234503415
    mul = 9
    data = [
        12062177936022666431,
        11490956213547313652,
        16829172008830410301,
        11899344311637024046,
        3757253942274655973,
        17835857420906997132,
        10787740079658512390,
        17590610739856314589,
    ]

    ret_values = tiger.tiger_pass(a, b, c, mul, data)

    assert ret_values["a"] == 1509595445172618351, (
        "a failed, " + str(ret_values["a"]) + " != 1509595445172618351"
    )
    assert ret_values["b"] == 206383248218352883, (
        "b failed, " + str(ret_values["b"]) + " != 206383248218352883"
    )
    assert ret_values["c"] == 2725617220977123037, (
        "c failed, " + str(ret_values["c"]) + " != 2725617220977123037"
    )


def test_tiger_compress() -> None:
    # input data for tiger_compress must be 64 bytes long
    x = b"TigerTigerTigerTigerTigerTigerTigerTigerTigerTigerTigerTigerTige"
    res = [81985529216486895, 18364758544493064720, 17336226011405279623]

    tiger.tiger_compress(x, res)
    assert res[0] == 0x29CCDEE812891C0F, "r1 failed, %X != 0x29CCDEE812891C0F" % res[0]
    assert res[1] == 0xA18BA64634ACD11A, "r2 failed, %X != 0xA18BA64634ACD11A" % res[1]
    assert res[2] == 0x5FA4D4854FCE7BCA, "r3 failed, %X != 0x5FA4D4854FCE7BCA" % res[2]


# The following are the test hashes provided by the example C implementation
def test_tiger_hash() -> None:
    assert tiger.hash(b"").hex() == "3293ac630c13f0245f92bbb1766e16167a4e58492dde73f3"
    assert (
        tiger.hash(b"abc").hex() == "2aab1484e8c158f2bfb8c5ff41b57a525129131c957b5f93"
    )
    assert (
        tiger.hash(b"Tiger").hex() == "dd00230799f5009fec6debc838bb6a27df2b9d6f110c7937"
    )
    assert (
        tiger.hash(
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"
        ).hex()
        == "f71c8583902afb879edfe610f82c0d4786a3a534504486b5"
    )
    assert (
        tiger.hash(
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ=abcdefghijklmnopqrstuvwxyz+0123456789"
        ).hex()
        == "48ceeb6308b87d46e95d656112cdf18d97915f9765658957"
    )
    assert (
        tiger.hash(
            b"Tiger - A Fast New Hash Function, by Ross Anderson and Eli Biham"
        ).hex()
        == "8a866829040a410c729ad23f5ada711603b3cdd357e4c15e"
    )
    assert (
        tiger.hash(
            b"Tiger - A Fast New Hash Function, by Ross Anderson and"
            b" Eli Biham, proceedings of Fast Software Encryption 3, Cambridge."
        ).hex()
        == "ce55a6afd591f5ebac547ff84f89227f9331dab0b611c889"
    )
    assert (
        tiger.hash(
            b"Tiger - A Fast New Hash Function, by Ross Anderson and"
            b" Eli Biham, proceedings of Fast Software Encryption 3, Cambridge, 19"
            b"96."
        ).hex()
        == "631abdd103eb9a3d245b6dfd4d77b257fc7439501d1568dd"
    )
    assert (
        tiger.hash(
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz01"
            b"23456789+-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz012345"
            b"6789+-"
        ).hex()
        == "c54034e5b43eb8005848a7e0ae6aac76e4ff590ae715fd25"
    )
