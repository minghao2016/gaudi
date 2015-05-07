#!/usr/bin/python

##############
# GAUDIasm: Genetic Algorithms for Universal
# Design Inference and Atomic Scale Modeling
# Authors:  Jaime Rodriguez-Guerra Pedregal
#            <jaime.rodriguezguerra@uab.cat>
#           Jean-Didier Marechal
#            <jeandidier.marechal@uab.cat>
# Web: https://bitbucket.org/jrgp/gaudi
##############

# Python
from collections import OrderedDict
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import os
import pprint
import math
# Chimera
import chimera
# External dependencies
import deap.base
import yaml
# GAUDI
import gaudi.plugin

pp = pprint.PrettyPrinter(4)


class Individual(object):

    """
    Base class for `individual` objects that are evaluated by DEAP.

    Each individual is a potential solution.
    It contains all that is needed for an evaluation. With multiprocessing in mind,
    individuals should be self-contained so it can be passed between threads.
    This replaces the need for all that initialization scripting in launch.py.

    :genes:    A dict containing parsed features (genes) for the solution
    :environment:   Constants of the system
    """

    _CACHE = {}
    _CACHE_OBJ = {}

    def __init__(self, cfg=None, cache=None, ):
        self.genes = OrderedDict()
        self.cfg = cfg
        gaudi.plugin.load_plugins(self.cfg.genes, container=self.genes,
                                  cache=self._CACHE, parent=self,
                                  cxeta=self.cfg.ga.cx_eta,
                                  mteta=self.cfg.ga.cx_eta,
                                  indpb=self.cfg.ga.mut_indpb)
        self.fitness = gaudi.base.Fitness(parent=self, cache=self._CACHE_OBJ)

    def evaluate(self):
        self.express()
        score = self.fitness.evaluate()
        self.unexpress()
        return score

    def express(self):
        """
        Express genes in this environment. Very much like 'compiling' the
        individual to a chimera.Molecule.
        """
        for name, gene in self.genes.items():
            print "Expressing gene", name, "with allele"
            pp.pprint(gene.allele)
            gene.express()

    def unexpress(self):
        """
        Undo .express()
        """
        for gene in reversed(self.genes.values()):
            gene.unexpress()

    def mate(self, individual):
        for gene in self.genes.values():
            gene.mate(individual.genes[gene.name])

        return self, individual

    def mutate(self, indpb):
        for gene in self.genes.values():
            gene.mutate(indpb)
        return self,

    def similar(self, individual):
        self.express()
        individual.express()
        compound1 = next(compound for compound in self.genes.values()
                         if compound.__class__.__name__ == 'Molecule')
        compound2 = next(compound for compound in individual.genes.values()
                         if compound.__class__.__name__ == 'Molecule')

        xf1, xf2 = compound1.mol.openState.xform, compound2.mol.openState.xform
        atoms1 = sorted(compound1.mol.atoms, key=lambda x: x.serialNumber)
        atoms2 = sorted(compound2.mol.atoms, key=lambda x: x.serialNumber)
        sqdist = sum(xf1.apply(a.coord()).sqdistance(xf2.apply(a.coord()))
                     for a, b in zip(atoms1, atoms2))
        rmsd = math.sqrt(sqdist / ((len(atoms1) + len(atoms2)) / 2.0))

        self.unexpress()
        individual.unexpress()

        print "RMSD is", rmsd, "which means its similarity is", rmsd < self.cfg.ga.similarity_rmsd
        return rmsd < self.cfg.ga.similarity_rmsd

    def write(self, path, name, i, compress=True):
        """
        # Maybe someday we can pickle it all :/
        filename = os.path.join(path, '{}_{}.pickle.gz'.format(name,i))
        with gzip.GzipFile(filename, 'wb') as f:
            cPickle.dump(self, f, 0)
        return filename
        """
        COMPRESS = ZIP_DEFLATED if compress else ZIP_STORED
        self.express()
        zipfilename = os.path.join(path, '{}__{:03d}.zip'.format(name, i))
        with ZipFile(zipfilename, 'w', COMPRESS) as z:
            output = OrderedDict()
            for gene in self.genes.values():
                print "Writing", gene.name
                filename = gene.write(path, name)
                if filename:
                    z.write(filename, os.path.basename(filename))
                    os.remove(filename)
                    output[gene.name] = os.path.basename(filename)
            try:
                output['score'] = list(self.fitness.values)
            except AttributeError:  # fitness not in individual :/
                raise
            z.writestr('{}__{:03d}.gaudi'.format(name, i),
                       yaml.dump(output, default_flow_style=False))
        self.unexpress()
        return zipfilename


class Fitness(deap.base.Fitness):

    """
    Augmented `Fitness` class to self-include `objectives` objects.

    It subclasses  DEAP's `Fitness` to include details of objectives being evaluated
    and a function to evaluate them all at once. Since Fitness it's an Attribute
    of every `individual`, it should result in a self-contained object.
    """

    objectives = OrderedDict()
    wvalues = ()

    def __init__(self, parent=None, cache=None, *args, **kwargs):
        self.parent = parent
        self.weights = self.parent.cfg.weights
        deap.base.Fitness.__init__(self, *args, **kwargs)
        self.cache = cache
        self.env = chimera.selection.ItemizedSelection()

        if not self.objectives:
            gaudi.plugin.load_plugins(self.parent.cfg.objectives,
                                      container=self.objectives,
                                      cache=self.cache, parent=self.parent,
                                      environment=self.env)

    def __deepcopy__(self, memo):
        copy_ = self.__class__(parent=self.parent)
        copy_.wvalues = self.wvalues
        return copy_

    def evaluate(self):
        score = []
        for name, obj in self.objectives.items():
            print "Evaluating", name
            score.append(obj.evaluate())
        return score
