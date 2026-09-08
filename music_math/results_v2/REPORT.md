# Alien-Math Music Experiment — Run 2

Analyzed **80** tracks. Category labels were withheld until post-hoc evaluation.

## Blind category recovery

Scalar phenotype NN: **20.0%** vs chance **11.4%**; permutation p=0.005997.
Reaction-network phenotype NN: **25.0%** vs chance **11.4%**; permutation p=0.004498.

## Alien axes

- Axis 1 (27.2% variance): detailed_balance_violation (+0.33), triplet_irreversibility (+0.33), transition_entropy_norm (+0.31), self_retention (-0.31), speed_mean (+0.30), entropy_norm (+0.29)
- Axis 2 (23.5% variance): rqa_determinism (+0.36), rqa_laminarity (+0.33), rqa_mean_diag (+0.33), rqa_trapping_time (+0.32), rqa_recurrence_rate (+0.31), rqa_max_diag (+0.30)
- Axis 3 (10.2% variance): permutation_entropy (+0.47), statistical_complexity (-0.44), turn_angle_mean (+0.42), topo_h1_entropy (-0.28), topo_h1_count (-0.27), speed_cv (-0.24)
- Axis 4 (6.2% variance): topo_h1_max (+0.39), topo_h1_sig_count (+0.38), heat_capacity (-0.33), free_energy_range (-0.31), hurst_pc1 (+0.26), time_asymmetry_tau1 (+0.25)
- Axis 5 (4.9% variance): tortuosity (+0.52), rqa_max_diag (+0.32), metastability_slem (-0.30), topo_h1_count (+0.26), rqa_mean_diag (+0.25), rqa_trapping_time (+0.24)

## Strong temporal-null effects

- shuffle / metastability_slem: median original-control +0.5883 (100% positive)
- phase_randomized / metastability_slem: median original-control +0.5679 (100% positive)
- phase_randomized / topo_h1_total: median original-control -0.4061 (32% positive)
- shuffle / self_retention: median original-control +0.2771 (100% positive)
- phase_randomized / transition_entropy_norm: median original-control +0.2211 (88% positive)
- shuffle / hurst_pc1: median original-control +0.2031 (95% positive)
- phase_randomized / self_retention: median original-control -0.1880 (26% positive)
- phase_randomized / rqa_mean_diag: median original-control +0.1838 (92% positive)
- shuffle / rqa_mean_diag: median original-control +0.1659 (94% positive)
- phase_randomized / rqa_laminarity: median original-control +0.1657 (90% positive)
- phase_randomized / rqa_determinism: median original-control +0.1439 (94% positive)
- shuffle / transition_entropy_norm: median original-control -0.1341 (0% positive)

Persistent homology is computed on the state-space point cloud and is intentionally not expected to change under simple temporal shuffling; RQA and order statistics are the temporal geometry tests.
