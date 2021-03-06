"""
Created by Emille Ishida in May, 2015.

Function for performing Gaussian Process fit using gptools.

- imp_gptools:
         Perform Gaussian Process with gptools through MCMC.

- fit_LC:
         Gaussian Process fit using gptools.
"""

import numpy as np
import gptools
import os

def imp_gptools(data, fil, mcmc=True, p=None):
    """
    Perform Gaussian Process with gptools through MCMC.

    input: data, dict
           dictionary of raw data
           output from read_snana_lc
           keys: filters

           fil, str
           filter
        
           mcmc, bool, optional
           if True, optimize kernel parameters using mcmc
           Default is True

           p, list of integers
           lower and upper bound where the GP fit is required
           if None use min and max values from mjd data
           default is None

    output: data, dict
            updated dictionary with GP results
    """
    # format data
    mjd = data[fil][:, 0]
    flux = data[fil][:, 1]
    fluxerr = data[fil][:, 2]

    absflux = [abs(item) for item in flux]

    # setup GP
    k_obj = gptools.SquaredExponentialKernel(param_bounds=[(0, max(absflux)),
                                             (0, np.std(mjd))])
    data['GP_obj'][fil] = gptools.GaussianProcess(k_obj)
    data['GP_obj'][fil].add_data(mjd, flux, err_y=fluxerr)

    if p == None:
        data['xarr'][fil] = np.arange(min(mjd), max(mjd), 0.2)
    else:
        data['xarr'][fil] = np.arange(min(mjd)-100, max(mjd)+100, 0.2)

    if mcmc:
        out = data['GP_obj'][fil].predict(data['xarr'][fil], use_MCMC=True, full_MCMC=True,
                                          return_std=False,
                                          num_proc=int(data['n_proc'][0]),
                                          nsamp=int(data['nsamp_mcmc'][0]),
                                          plot_posterior=False,
                                          plot_chains=False,
                                          burn=int(data['burn'][0]),
                                          thin=int(data['thin'][0]))

    else:
        data['GP_obj'][fil].optimize_hyperparameters()
        out = data['GP_obj'][fil].predict(data['xarr'][fil], use_MCMC=False)

    data['GP_fit'][fil] = out[0]
    data['GP_std'][fil] = out[1]

    del out
    del k_obj

    return data


def save_result(data, mean=True, samples=False):
    """
    Save results of GP fit to file.

    input: data, dict
           dictionary of raw data
           output from read_snana_lc
           keys: filters

           mean, bool - optional
           if True, save mean GP fit
           Default is True

           samples, bool - optional
           if True, save draws from GP fit
           Default is False
    """
    # check if storage directory exsts
    if not os.path.exists(data['samples_dir'][0]):
        os.makedirs(data['samples_dir'][0])

    if samples:
        op1 = open(data['samples_dir'][0] + data['file_root'][0] +
                   data['SNID:'][0] + '_' + data['measurement'][0] + '_samples.dat', 'w')
        op1.write('filter    MJD    ')
        xfil = data['filters'][0]
        for j in xrange(len(data['realizations'][xfil])):
            op1.write('samp' + str(j + 1) + '    ')
        op1.write('\n')
        for fil in data['filters']:
            for i in xrange(len(data['xarr'][fil])):
                op1.write(fil + '    ' +
                          str(data['xarr'][fil][i]) + '    ')
                if data['measurement'][0] == 'flux':
                    for j in xrange(len(data['realizations'][xfil])):
                        op1.write(str(data['realizations'][fil][j][i]) +
                                  '    ')
                else:
                    for j in xrange(len(data['realizations'][xfil])):
                        op1.write(str(-data['realizations'][fil][j][i]) +
                                      '    ')
                op1.write('\n')
        op1.close()

    if mean:
        op2 = open(data['samples_dir'][0] + data['file_root'][0] +
                   data['SNID:'][0] + '_' + data['measurement'][0] + '_mean.dat', 'w')
        op2.write('filter    MJD    GP_fit     GP_std')
        if 'SIM_NON1a:' in data.keys():
                op2.write('    type\n')
        else:
            op2.write('\n')

        for fil in data['filters']:
            for k in xrange(len(data['xarr'][fil])):
                if data['measurement'][0] == 'flux':
                    op2.write(fil + '    ' + str(data['xarr'][fil][k]) +
                              '    ' + str(data['GP_fit'][fil][k]) +
                              '    ' + str(data['GP_std'][fil][k]))
                else:
                    op2.write(fil + '    ' + str(data['xarr'][fil][k]) +
                              '    ' + str(-data['GP_fit'][fil][k]) +
                              '    ' + str(data['GP_std'][fil][k]))
                if 'SIM_NON1a:' in data.keys():
                    op2.write('    ' + str(data['SIM_NON1a:'][0]) + '\n')
                else:
                    op2.write('\n')
        op2.close()


def samp_mcmc(fil, data, screen=False):

    if screen:
        print '... ... calculate samples'

    # update hyperparameters values
    sampler = data['GP_obj'][fil].sample_hyperparameter_posterior()
    flat_trace = sampler.chain[:, int(data['nsamp_mcmc'][0])::int(data['burn'][0]), :]
    flat_trace = flat_trace.reshape((-1, flat_trace.shape[2]))

    draws = []
    indx = 0
    while len(draws) < int(data['n_samples'][0]):

        indx = indx + 1
        par1 = flat_trace[indx][0]
        par2 = flat_trace[indx][1]
        par3 = data['GP_obj'][fil].update_hyperparameters(np.array([par1,par2]))

        new_out = data['GP_obj'][fil].draw_sample(data['xarr'][fil]).T[0]

        flag = 0
        for l in xrange(len(data['xarr'][fil])):
            vmin = data['GP_fit'][fil][l] - data['GP_std'][fil][l]
            vmax = data['GP_fit'][fil][l] + data['GP_std'][fil][l]
            if new_out[l] < vmin and new_out[l] > vmax:
                flag = flag + 1

        if flag == 0:
            draws.append(new_out)
        elif screen:
            print 'Discharged!'

        del new_out

    del sampler
    del flat_trace

    return np.array(draws)


def run_filters(data, fil, do_mcmc, screen=False, mean=True, samples=False, predict=None):


    if screen:
        print '... filter: ' + fil

    if mean:
        data = imp_gptools(data, fil, mcmc=do_mcmc, p=predict)

    if samples and int(data['n_samples'][0]) > 0:

        if do_mcmc:
            draws = samp_mcmc(fil, data, screen=screen)
        else:
            data['GP_obj'][fil].optimize_hyperparameters()
            draws = data['GP_obj'][fil].draw_sample(data['xarr'][fil],
                                        num_samp=int(data['n_samples'][0])).T

        data['realizations'][fil] = draws

    return data

           

def fit_lc(data, mean=True, samples=False, screen=False, do_mcmc=True,
           save_mean=True, save_samples=False, predict=None):
    """
    Gaussian Process fit using gptools.

    input:  data -> dictionary of raw data
                    output from read_snana_lc
                    keys: filters

            mean -> bool, optional
                    if True, calculate mean GP fit
                    Default is True

            samples -> bool, optional
                       if True, calculate samples from the final GP
                       Default is False

            screen -> bool, optional
                      if True, print calculation steps into screen
                      Default is False

            do_mcmc -> bool, optional
                       if True, optimize kernel parameters using mcmc
                       Default is True

            save_mean -> bool, optional
                         if True save mean GP fit to file
                         Default is True

            save_samples -> bool, optional
                            if True save GP draws to file
                            Default is False

    output: data -> update dictionary with new keyword:
                    realizations
    """
    key_list = ['realizations', 'xarr', 'GP_std', 'GP_obj']

    for name in key_list:
        if name not in data.keys():
            data[name] = {}

    for fil in data['filters']:
        data = run_filters(data, fil, do_mcmc=do_mcmc, screen=screen,
                           mean=mean, samples=samples, predict=predict)

    save_result(data, mean=save_mean, samples=save_samples)

    if screen:
        print '\n'

    return data


def main():
    """Print documentation."""
    print __doc__

if __name__ == '__main__':
    main()
