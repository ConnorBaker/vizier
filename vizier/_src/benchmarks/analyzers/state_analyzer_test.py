# Copyright 2024 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import itertools
from vizier import benchmarks as vzb
from vizier import pyvizier as vz
from vizier._src.algorithms.designers import random
from vizier._src.benchmarks.analyzers import state_analyzer
from vizier.algorithms import designers
from vizier.benchmarks import experimenters
from absl.testing import absltest


class StateAnalyzerTest(absltest.TestCase):

  def test_curve_conversion(self):
    dim = 10
    experimenter = experimenters.BBOBExperimenterFactory('Sphere', dim)()

    def _designer_factory(config: vz.ProblemStatement, seed: int):
      return random.RandomDesigner(config.search_space, seed=seed)

    benchmark_state_factory = vzb.DesignerBenchmarkStateFactory(
        designer_factory=_designer_factory, experimenter=experimenter
    )
    num_trials = 20
    runner = vzb.BenchmarkRunner(
        benchmark_subroutines=[vzb.GenerateAndEvaluate()],
        num_repeats=num_trials,
    )

    states = []
    num_repeats = 3
    for i in range(num_repeats):
      bench_state = benchmark_state_factory(seed=i)
      runner.run(bench_state)
      states.append(bench_state)

    curve = state_analyzer.BenchmarkStateAnalyzer.to_curve(states)
    self.assertEqual(curve.ys.shape, (num_repeats, num_trials))

  def test_empty_curve_error(self):
    with self.assertRaisesRegex(ValueError, 'Empty'):
      state_analyzer.BenchmarkStateAnalyzer.to_curve([])

  def test_different_curve_error(self):
    exp1 = experimenters.BBOBExperimenterFactory('Sphere', dim=2)()
    exp2 = experimenters.BBOBExperimenterFactory('Sphere', dim=3)()

    def _designer_factory(config: vz.ProblemStatement, seed: int):
      return random.RandomDesigner(config.search_space, seed=seed)

    state1_factory = vzb.DesignerBenchmarkStateFactory(
        designer_factory=_designer_factory, experimenter=exp1
    )
    state2_factory = vzb.DesignerBenchmarkStateFactory(
        designer_factory=_designer_factory, experimenter=exp2
    )

    runner = vzb.BenchmarkRunner(
        benchmark_subroutines=[vzb.GenerateAndEvaluate()],
        num_repeats=10,
    )

    state1 = state1_factory()
    state2 = state2_factory()
    runner.run(state1)
    runner.run(state2)

    with self.assertRaisesRegex(ValueError, 'must have same problem'):
      state_analyzer.BenchmarkStateAnalyzer.to_curve([state1, state2])

  def test_record_conversion(self):
    dim = 10
    factory = experimenters.BBOBExperimenterFactory('Sphere', dim)
    experimenter = factory()

    def _designer_factory(config: vz.ProblemStatement, seed: int):
      return random.RandomDesigner(config.search_space, seed=seed)

    benchmark_state_factory = vzb.DesignerBenchmarkStateFactory(
        designer_factory=_designer_factory, experimenter=experimenter
    )
    num_trials = 20
    runner = vzb.BenchmarkRunner(
        benchmark_subroutines=[vzb.GenerateAndEvaluate()],
        num_repeats=num_trials,
    )

    states = []
    num_repeats = 3
    for i in range(num_repeats):
      bench_state = benchmark_state_factory(seed=i)
      runner.run(bench_state)
      states.append(bench_state)

    record = state_analyzer.BenchmarkStateAnalyzer.to_record(
        algorithm='random', experimenter_factory=factory, states=states
    )
    objective_curve = record.plot_elements['objective'].curve
    self.assertIsNotNone(objective_curve)
    self.assertEqual(objective_curve.ys.shape, (num_repeats, num_trials))
    self.assertEqual(record.algorithm, 'random')
    self.assertIn('Sphere', str(record.experimenter_metadata))
    self.assertIn(f'{dim}', str(record.experimenter_metadata))

  def test_add_comparison_metrics(self):
    function_names = ['Sphere', 'Discus']
    dimensions = [4, 8]
    product_list = list(itertools.product(function_names, dimensions))

    experimenter_factories = []
    for product in product_list:
      experimenter_factory = experimenters.BBOBExperimenterFactory(
          name=product[0], dim=product[1]
      )
      experimenter_factories.append(experimenter_factory)

    num_repeats = 5
    num_iterations = 20
    runner = vzb.BenchmarkRunner(
        benchmark_subroutines=[
            vzb.GenerateSuggestions(),
            vzb.EvaluateActiveTrials(),
        ],
        num_repeats=num_iterations,
    )
    algorithms = {
        'grid': designers.GridSearchDesigner.from_problem,
        'random': designers.RandomDesigner.from_problem,
    }

    records = []
    for experimenter_factory in experimenter_factories:
      for algo_name, algo_factory in algorithms.items():
        benchmark_state_factory = vzb.ExperimenterDesignerBenchmarkStateFactory(
            experimenter_factory=experimenter_factory,
            designer_factory=algo_factory,
        )
        states = []
        for _ in range(num_repeats):
          benchmark_state = benchmark_state_factory()
          runner.run(benchmark_state)
          states.append(benchmark_state)
        record = state_analyzer.BenchmarkStateAnalyzer.to_record(
            algorithm=algo_name,
            experimenter_factory=experimenter_factory,
            states=states,
        )
        records.append(record)

    compare_metric = state_analyzer.RECORD_OBJECTIVE_KEY
    baseline_algo = 'random'
    analyzed_records = (
        state_analyzer.BenchmarkRecordAnalyzer.add_comparison_metrics(
            records, baseline_algo='random', compare_metric='objective'
        )
    )
    for record in analyzed_records:
      self.assertIn(
          compare_metric + ':score:' + baseline_algo,
          record.plot_elements.keys(),
      )
      self.assertIn(
          compare_metric + ':score_curve:' + baseline_algo,
          record.plot_elements.keys(),
      )


if __name__ == '__main__':
  absltest.main()
