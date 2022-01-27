
import dag_simulation
from dag_simulation import *


def gen(D_factor):
	_lambda, _delta, _alpha = 1, 0.01, 0.01
	simulation = Simulation(_alpha, _delta, _lambda, k=18, D_factor=D_factor)
	# simulation.k = select_ghostdag_k(2 * simulation.D_max * _lambda, _delta)
	dag = simulation.run_simulation()
	# print_dag(dag)
	print('\n=========\n')
	# Print stats
	print('Delay factor: {}'.format(D_factor))
	print_stats(simulation.D_max, _delta, _lambda, dag, simulation.k)
	if not os.path.isdir('data'):
		os.mkdir('data')
	save_to_json(dag, file_name=os.path.join('data',
											 'wide-dag-blocks--2^{}-delay-factor--{}-k--{}.json'.format(
												 int(math.log2(dag_simulation.simulation_time)), D_factor, simulation.k)))


if __name__ == '__main__':
	dag_simulation.reindex_attack = False
	dag_simulation.simulation_time = 2 ** 10
	dag_simulation.print_progress = False

	for f in [1, 2, 4, 6, 8]:
		gen(D_factor=f)