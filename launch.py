#!/usr/bin/python

##############
# GAUDIasm: Genetic Algorithms for Universal
# Design Inference and Atomic Scale Modeling
# Author: Jaime Rodriguez-Guerra Pedregal
# Email: jaime.rogue@gmail.com
# Web: https://bitbucket.org/jrgp/gaudi
##############
# Python builtins
import sys, os, numpy
from time import strftime
from collections import OrderedDict
# Added dependencies
import deap, yaml
from deap import creator, tools, base, algorithms
# Custom modules
import gaudi

def main(cfg):
	gaudi.plugin.import_plugins(*cfg.genes)
	gaudi.plugin.import_plugins(*cfg.objectives)
	
	## DEAP setup: Fitness, Individuals, Population
	toolbox = deap.base.Toolbox()
	deap.creator.create("Fitness", gaudi.base.Fitness,
						objectivelist=cfg.objectives,
						weights=cfg.weights)
	deap.creator.create("Individual", gaudi.base.Individual, 
						fitness=deap.creator.Fitness)
	toolbox.register("call", (lambda fn, *args, **kwargs: fn(*args, **kwargs)))
	toolbox.register("individual", toolbox.call, deap.creator.Individual, cfg.genes, cfg=cfg)
	toolbox.register("population", deap.tools.initRepeat, list, toolbox.individual)
	population = toolbox.population(n=cfg.ga.pop)

	toolbox.register("evaluate", lambda ind: ind.evaluate())
	toolbox.register("mate", (lambda ind1, ind2: ind1.mate(ind2)))
	toolbox.register("mutate", (lambda ind, indpb: ind.mutate(indpb)), indpb=cfg.ga.mut_indpb)
	toolbox.register("similarity", (lambda ind1, ind2: ind1.similar(ind2)))
	toolbox.register("select", deap.tools.selNSGA2)

	if cfg.ga.history:
		history = deap.tools.History()
		# Decorate the variation operators
		toolbox.decorate("mate", history.decorator)
		toolbox.decorate("mutate", history.decorator)
		history.update(population)

	paretofront = deap.tools.ParetoFront(toolbox.similarity)
	stats = deap.tools.Statistics(lambda ind: ind.fitness.values)
	numpy.set_printoptions(precision=cfg.general.precision)
	stats.register("avg", numpy.mean, axis=0)
	stats.register("min", numpy.min, axis=0)
	stats.register("max", numpy.max, axis=0)
	population, log = deap.algorithms.eaMuPlusLambda(population, toolbox, 
		mu = int(cfg.ga.mu*cfg.ga.pop), lambda_= int(cfg.ga.lambda_*cfg.ga.pop), 
		cxpb=cfg.ga.cx_pb, mutpb=cfg.ga.mut_pb, 
		ngen=cfg.ga.gens, stats=stats, halloffame=paretofront)

	return population, log, paretofront

if __name__ == "__main__":	
	## Parse input
	try:
		cfg = gaudi.parse.Settings(sys.argv[1])
	except IndexError: 
		raise ValueError("Input file not provided")
	except IOError:
		raise IOError("Specified input file was not found")

	try: 
		os.makedirs(cfg.general.outputpath)
	except OSError:
		if not os.path.isdir(cfg.general.outputpath):
			raise
	# log = gaudi.parse.enable_logging(cfg.general.outputpath)
	# log.info("Starting GAUDI job")
	# log.info("Opened input file '{}'".format(sys.argv[1]))	
	# log.info("Scores:", ', '.join(o.name for o in cfg.objectives))
	pop, log, paretofront = main(cfg)


	results = OrderedDict()
	results['GAUDI.objectives'] = ['{} ({})'.format(obj.name, obj.type) for obj in cfg.objectives]
	results['GAUDI.results'] = OrderedDict()
	for i, ind in enumerate(paretofront):
		filename = ind.write(cfg.general.outputpath, cfg.general.name, i, cfg.general.compress)
		results['GAUDI.results'][filename] = list(ind.fitness.values)


	out = open(cfg.general.outputpath+cfg.general.name+'.gaudi.yaml', 'w+') 
	print >> out, '# Generated by GAUDI on {}'.format(strftime("%Y-%m-%d %H:%M:%S"))
	print >> out, yaml.dump(results, default_flow_style=False)
	out.close()