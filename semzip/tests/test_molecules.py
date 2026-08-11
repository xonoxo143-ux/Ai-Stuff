import unittest

from semzip.molecules import (
    borrow,
    buy,
    enter,
    give,
    leave,
    lend,
    receive,
    sell,
    size_change,
    temperature_change,
)


class MoleculeTests(unittest.TestCase):
    def test_give_receive_converge(self):
        self.assertEqual(
            give("john", "mary", "book"),
            receive("mary", "book", "john"),
        )

    def test_buy_sell_converge(self):
        self.assertEqual(
            buy("mary", "book", "john", "ten_dollars"),
            sell("john", "mary", "book", "ten_dollars"),
        )

    def test_borrow_lend_converge(self):
        self.assertEqual(
            borrow("mary", "book", "john"),
            lend("john", "mary", "book"),
        )

    def test_loan_is_not_plain_gift(self):
        self.assertNotEqual(
            borrow("mary", "book", "john"),
            give("john", "mary", "book"),
        )

    def test_enter_and_leave_are_location_change(self):
        entering = enter("john", "kitchen")
        leaving = leave("john", "kitchen")
        self.assertEqual(entering.atom("DIMENSION"), "location")
        self.assertEqual(leaving.atom("DIMENSION"), "location")
        self.assertEqual(entering.atom("AFTER"), "kitchen")
        self.assertEqual(leaving.atom("BEFORE"), "kitchen")

    def test_heat_and_growth_share_change_shape(self):
        heat = temperature_change("water", "cold", "hot")
        grow = size_change("plant", "small", "large")
        self.assertEqual(heat.operator, "CHANGE")
        self.assertEqual(grow.operator, "CHANGE")
        self.assertNotEqual(heat.atom("DIMENSION"), grow.atom("DIMENSION"))


if __name__ == "__main__":
    unittest.main()
