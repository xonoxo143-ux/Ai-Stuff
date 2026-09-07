import unittest

import torch

from fluidlm import FluidConfig, FluidLM


class FluidLMTests(unittest.TestCase):
    def test_forward_shapes_and_normalized_density(self):
        torch.manual_seed(1)
        model = FluidLM(FluidConfig(vocab_size=13, grid_size=4))
        tokens = torch.randint(0, 13, (3, 7))
        logits, (rho, velocity) = model(tokens)

        self.assertEqual(tuple(logits.shape), (3, 7, 13))
        self.assertEqual(tuple(rho.shape), (3, 4, 4))
        self.assertEqual(tuple(velocity.shape), (3, 2, 4, 4))
        self.assertTrue(torch.isfinite(logits).all())
        self.assertTrue(torch.isfinite(rho).all())
        self.assertTrue(torch.isfinite(velocity).all())

        mass = rho.sum(dim=(-2, -1))
        self.assertTrue(torch.allclose(mass, torch.ones_like(mass), atol=1e-5))

    def test_uniform_unforced_state_stays_symmetric(self):
        model = FluidLM(FluidConfig(vocab_size=5, grid_size=4))
        with torch.no_grad():
            model.token_drive.weight.zero_()

        state = model.init_state(batch_size=2)
        token = torch.zeros(2, dtype=torch.long)
        _, (rho, velocity) = model.step(token, state)

        expected = torch.full_like(rho, 1.0 / 16.0)
        self.assertTrue(torch.allclose(rho, expected, atol=1e-5))
        self.assertTrue(torch.allclose(velocity, torch.zeros_like(velocity), atol=1e-6))

    def test_constant_velocity_has_zero_vorticity(self):
        velocity = torch.ones((2, 2, 5, 5))
        vort = FluidLM.vorticity(velocity)
        self.assertTrue(torch.allclose(vort, torch.zeros_like(vort)))

    def test_token_force_does_not_add_net_momentum(self):
        torch.manual_seed(7)
        model = FluidLM(FluidConfig(vocab_size=8, grid_size=5))
        rho, velocity = model.init_state(batch_size=3)
        token = torch.tensor([1, 2, 3], dtype=torch.long)
        _, (_, next_velocity) = model.step(token, (rho, velocity))

        mean_velocity = next_velocity.mean(dim=(-2, -1))
        self.assertTrue(
            torch.allclose(mean_velocity, torch.zeros_like(mean_velocity), atol=1e-6)
        )


if __name__ == "__main__":
    unittest.main()
