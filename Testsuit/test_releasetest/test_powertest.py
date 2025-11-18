import sys

import pytest

from Testsuit.test_releasetest.env import canoe


def test_simple_case():
    """简单测试用例"""
    canoe.start_measurement()
    canoe.compile_all_capl_nodes()
    F18A = canoe.diag_PHY('22' + "F18A")
    F188 = canoe.diag_PHY('22' + "F188")
    F191 = canoe.diag_PHY('22' + "F191")
    F1CB = canoe.diag_PHY('22' + "F1CB")
    F192 = canoe.diag_PHY('22' + "F192")
    F193 = canoe.diag_PHY('22' + "F193")
    F194 = canoe.diag_PHY('22' + "F194")
    F195 = canoe.diag_PHY('22' + "F195")
    DID202C = canoe.diag_PHY('22' + "202C")
    F1C1 = canoe.diag_PHY('22' + "F1C1")
    DID202B = canoe.diag_PHY('22' + "202B")
    F180 = canoe.diag_PHY('22' + "F180")



if __name__ == "__main__":

    # 运行pytest
    pytest.main()


