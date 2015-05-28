"""
Created by Emille Ishida in May, 2015.

Class to implement calculations on data matrix.
"""

import os
import sys

import numpy as np
from multiprocessing import Pool

from snclass.treat_lc import LC
from snclass.util import read_user_input, read_snana_lc
from snclass.functions import core_cross_val

##############################################


class DataMatrix(object):

    """
    Data matrix class.

    Methods:
        - build: Build data matrix according to user input file specifications.
        - reduce_dimension: Perform dimensionality reduction.
        - cross_val: Perform cross-validation.

    Attributes:
        - user_choices: dict, user input choices
        - snid: vector, list of objects identifiers
        - datam: array, data matrix for training
        - redshift: vector, redshift for training data
        - sntype: vector, classification of training data
        - low_dim_matrix: array, data matrix in KernelPC space
        - transf_test: function, project argument into KernelPC space
        - final: vector, optimize parameter values
    """

    def __init__(self, input_file=None):
        """
        Read user input file.

        input: input_file -> str
               name of user input file
        """
        self.datam = None
        self.snid = None
        self.redshift = None
        self.sntype = None
        self.low_dim_matrix = None
        self.transf_test = None
        self.final = None

        if input_file is not None:
            self.user_choices = read_user_input(input_file)

    def build(self, file_out=None):
        """
        Build data matrix according to user input file specifications.

        input:   file_out -> str, optional
                 file to store data matrix (str). Default is None
        """
        # list all files in sample directory
        file_list = os.listdir(self.user_choices['samples_dir'][0])

        datam = []
        self.snid = []
        redshift = []
        sntype = []

        for obj in file_list:
            if 'mean' in obj:

                # take object identifier
                name = obj[len('DES_SN'):-len('_mean.dat')]

                if len(name) == 5:
                    name = '0' + name
                elif len(name) == 4:
                    name = '00' + name

                self.user_choices['path_to_lc'] = ['DES_SN' + name + '.DAT']

                # read light curve raw data
                raw = read_snana_lc(self.user_choices)

                # initiate light curve object
                lc_obj = LC(raw, self.user_choices)

                # load GP fit
                lc_obj.load_fit_GP()

                # normalize
                lc_obj.normalize()

                # shift to peak mjd
                lc_obj.mjd_shift()

                # check epoch requirements
                lc_obj.check_epoch()

                if lc_obj.epoch_cuts:
                    # build data matrix lines
                    lc_obj.build_steps()

                    # store
                    obj_line = []
                    for fil in self.user_choices['filters']:
                        for item in lc_obj.flux_for_matrix[fil]:
                            obj_line.append(item)

                    rflag = self.user_choices['redshift_flag'][0]

                    datam.append(obj_line)
                    self.snid.append(raw['SNID:'][0])
                    redshift.append(raw[rflag][0])
                    sntype.append(raw[self.user_choices['type_flag'][0]][0])

        self.datam = np.array(datam)
        self.redshift = np.array(redshift)
        self.sntype = np.array(sntype)

        # write to file
        if file_out is not None:
            op1 = open(file_out, 'w')
            op1.write('SNID    type    z   LC...\n')
            for i in xrange(len(datam)):
                op1.write(str(self.snid[i]) + '    ' + str(self.sntype[i]) +
                          '    ' + str(self.redshift[i]) + '    ')
                for j in xrange(len(datam[i])):
                    op1.write(str(datam[i][j]) + '    ')
                op1.write('\n')
            op1.close()

    def reduce_dimension(self):
        """
        Perform dimensionality reduction with user defined funciton.

        input: pars - dict
               Dictionary of parameters.
               Must include all keywords required by
               self.user_choices['dim_reduction_func']() function.
        """
        # define dimensionality reduction function
        func = self.user_choices['dim_reduction_func']

        # reduce dimensionality
        self.low_dim_matrix = func(self.datam, self.user_choices)

        # define transformation function
        self.transf_test = func(self.datam, self.user_choices, transform=True)

    def cross_val(self):
        """Optimize the hyperparameters for RBF kernel and ncomp."""
        # correct type parameters if necessary
        types_func = self.user_choices['transform_types_func']
        if self.user_choices['transform_types_func'] is not None:
            self.sntype = types_func(self.sntype)

        # initialize parameters
        data = self.datam
        types = self.sntype
        choices = self.user_choices

        parameters = [data, types, choices] *
                      self.user_choices['n_cross_val_particles']

        if int(self.user_choices['n_proc'][0]) > 0:
            cv_func = self.user_choices['cross_validation_func']
            pool = Pool(processes=int(self.user_choices['nproc'][0]))
            my_pool = pool.map_async(cv_func, parameters)
            try:
                results = my_pool.get(0xFFFF)
            except KeyboardInterrupt:
                print 'Interruputed by the user!'
                sys.exit()

            pool.close()
            pool.join()

        else:
            number = self.user_choices['n_cross_val_particles']
            results = np.array([core_cross_val(data, types, choices)
                               for attempt in xrange(number)])

        indx_max = list(results[:, -1]).index(max(results[:, -1]))

        self.final = {}
        for i in xrange(len(self.user_choices['cross_val_par'])):
            par_list = self.user_choices['cross_val_par']
            self.final[par_list[i]] = results[indx_max][i]


def main():
    """Print documentation."""
    print __doc__

if __name__ == '__main__':
    main()
