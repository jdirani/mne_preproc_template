# J.Dirani

# epochs rejection based on log files not included


# ----------File structure-----------#
# ROOT>
#     MRI>
#         subjs
#     MEG>
#         subjs
#     STC>


import mne, eelbrain, os, glob, pickle
import numpy as np
import pandas as pd
from os.path import join
%gui qt
mne.set_log_level(verbose='WARNING')

#=========Edit here=========#
expt = 'TwoTones' #experiment name as written on the -raw.fif
ROOT = '/Users/my_user/data_file/'
subjects_dir = os.path.join(ROOT, 'MRI')
subjects = [i for i in os.listdir(ROOT+'MEG') if i.startswith('A0')]
event_id = dict(hi=223, lo=191) #conditions associated with each trigger
os.chdir(ROOT) #setting current dir

epoch_tmin = -0.1
epoch_tmax = 0.6
epoch_baseline = (-0.1,0)
decim = 1
equalize_epochs = False
expected_nb_events = 136

photodiode_realignment = True
SNR = 3 # 3 for ANOVAs, 2 for single trial analyses
fixed = False # False for orientation free, True for fixed orientation
#===========================#


'''==========================================================================='''
'''                           PART 1: Filter, bads, ICA                       '''
'''==========================================================================='''

# ------------------ Check which subj dont have ICA files --------------------- #
#Looks for a ..._ICA-raw.fif file. Post ICA+filtered data must be named accordingly
#Not necessary, just a quick way to check how many ICAs are left before running the loops
No_ica=[]
for subj in subjects:
    if os.path.isfile('MEG/%s/%s_%s_ICA-raw.fif'%(subj, subj, expt)):
        print 'ICA and filtering already done for subj=%s'%subj
    else:
        No_ica.append(subj)
print ">> ICA not done for %s (%s)" %(No_ica, len(No_ica))


# ----------------------------------- ICA ------------------------------------ #
# compute and save ICA
for subj in subjects:
    print subj
    if not os.path.isfile('MEG/%s/%s-ica.fif'%(subj,subj)):
        print 'importing raw...'
        raw = mne.io.read_raw_fif('MEG/%s/%s_%s-raw.fif' %(subj, subj, expt), preload=True)
        raw.filter(0,40, method='iir')
        ica = mne.preprocessing.ICA(n_components=0.95, method='fastica')
        print 'fitting ica...'
        # reject = dict(mag=2e-12) # Use this in ica.fit if too mnoisy
        ica.fit(raw) #reject=reject
        ica.save('MEG/%s/%s-ica.fif'%(subj,subj))
        del raw, ica

# Plot to make rejections
for subj in subjects:
    print subj
    if not os.path.isfile('MEG/%s/%s_%s_ICA-raw.fif' %(subj,subj, expt)):
        raw = mne.io.read_raw_fif('MEG/%s/%s_%s-raw.fif' %(subj, subj, expt), preload=True)
        raw.filter(0,40, method='iir')
        ica = mne.preprocessing.read_ica('MEG/%s/%s-ica.fif'%(subj,subj))
        ica.plot_sources(raw)
        raw_input('Press enter to continue')
        print 'Saving...'
        raw = ica.apply (raw, exclude=ica.exclude)
        raw.save('MEG/%s/%s_%s_ICA-raw.fif' %(subj,subj, expt))
        print 'Saving...'
        del raw, ica




'''==========================================================================='''
'''                             PART 2: get epochs                            '''
'''==========================================================================='''

for subj in subjects:
    print '>>  Getting epochs: subj=%s'%subj
    if os.path.isfile('MEG/%s/%s-epo.fif' %(subj,subj)):
        print '>> EPOCHS ALREADY CREATED FOR SUBJ=%s'%subj
    else:
        print "%s: Importing filtered+ICA data" %subj
        raw = mne.io.read_raw_fif('MEG/%s/%s_%s_ICA-raw.fif' %(subj, subj, expt), preload=True)
        #-----------------------------Find events------------------------------#
        print "%s: Finding events..." %subj
        events = mne.find_events(raw,min_duration=0.002)
        assert(len(events) == expected_nb_events)
        picks_meg = mne.pick_types(raw.info, meg=True, eeg=False, eog=False, stim=False)

        #-----------------------Fix photodiode shift---------------------------#
        if photodiode_realignment == True:
            photodiode = mne.find_events(raw,stim_channel='MISC 010',min_duration=0.005)
            if len(events) != len(photodiode):
                raise ValueError('Length of photodiode and events dont match.')
            delays = []
            for i in range(len(events)):
                delay = photodiode[i][0] - events[i][0]
                delays.append(delay)
            raw_input('Average photodiode delay = %s. Ok?' %(np.mean(delays)))
            print 'Realigning events...'
            for i in range(len(events)):
                events[i][0] = photodiode[i][0]

        #----------------------Reject epochs based on logs---------------------#
        # print "Rejecting epochs based on logs"
        # logfile_dir = 'MEG/%s/initial_output/%s_log_mask.csv' %(subj,subj)
        # logfile = pd.read_csv(logfile_dir)
        # logfile['epochs_mask'] = np.where(logfile['mask']==1, True, False)
        #
        epochs = mne.Epochs(raw, events, event_id=event_id, tmin=epoch_tmin, tmax=epoch_tmax, baseline=epoch_baseline, picks=picks_meg, decim=decim, preload=True)
        #
        # epochs = epochs[logfile.ep_mask]
        # del logfile

        #----------------------Manual epochs rejection-------------------------#
        print ">> Epochs rejection for subj=%s" %subj
        if os.path.isfile('MEG/%s/%s_rejfile.pickled' %(subj, subj)):
            print 'Rejections file for %s exists, loading file...' %(subj)
            rejfile = eelbrain.load.unpickle('MEG/%s/%s_rejfile.pickled' %(subj, subj))
            rejs = rejfile['accept'].x
            epochs_rej=epochs[rejs]
            print 'Done.'
        else:
            print 'Rejections file for %s does not exist, opening GUI...' %(subj)
            eelbrain.gui.select_epochs(epochs, vlim=2e-12, mark=['MEG 087','MEG 130'])
            raw_input('NOTE: Save as MEG/%s/%s_rejfile.pickled. \nPress enter when you are done rejecting epochs in the GUI...'%(subj,subj))

            # Marking bad channels
            bad_channels = raw_input('\nMarking bad channels:\nWrite bad channels separated by COMMA (e.g. MEG 017, MEG 022)\nIf no bad channels, press enter\n>')
            if bad_channels == '':
                del bad_channels
            else:
                bad_channels = bad_channels.split(', ')
                epochs.interpolate_bads(bad_channels)
                del bad_channels
            # Reject marked epochs
            rejfile = eelbrain.load.unpickle('MEG/%s/%s_rejfile.pickled' %(subj, subj))
            rejs = rejfile['accept'].x
            epochs_rej = epochs[rejs]

        # equalize events
        if equalize_epochs == True:
            print "equalizing epochs..."
            len_epochs_rej = len(epochs_rej) #because epochs_rej will be overwritten. Need this to later log to info.csv
            epochs_eq, eq_ids = epochs_rej.equalize_event_counts(event_id) #ids used later to log into info.csv
        else:
            print "not equalizing epochs."
            epochs_eq = epochs_rej.copy()
            eq_ids = []
            len_epochs_rej = len(epochs_rej)

        print '%s: bad epochs rejected' %subj



        #------------------Save raw.info and epochs to file-------------------#
        print 'Saving epochs to file...'
        info = raw.info
        pickle.dump(info, open('MEG/%s/%s-info.pickled' %(subj,subj), 'wb'))
        epochs_eq.save('MEG/%s/%s-epo.fif' %(subj,subj))

        # write rejection info to csv
        nb_accuracy_rej = np.unique(accuracy_mask, return_counts=True)[1][0]
        nb_noise_rej = np.unique(rejs, return_counts=True)[1][0]
        with open('MEG/%s/info/rej_info.csv'%subj, 'w') as f:
            f.write('accuracy_rej,noise_rej,good,equalize_counts,equalize_dropped,remaining_after_equalize\n')
            f.write('%s,%s,%s,%s,%s,%s\n'%(nb_accuracy_rej, nb_noise_rej, len_epochs_rej, equalize_epochs, len(eq_ids),len(epochs_eq)))
            f.close()

        # Write epochs counts per condition to csv
        with open('MEG/%s/info/epo_count.csv'%subj, 'w') as f:
            for cond in event_id.keys():
                f.write('%s,%s\n'%(cond, len(epochs_eq[cond])))
            f.close()

        del raw
        print 'Done.'



'''==========================================================================='''
'''                             PART 3: Create STCs                           '''
'''==========================================================================='''
for subj in subjects:
    if os.path.exists('STC/%s'%subj):
        print 'STCs ALREADY CREATED FOR SUBJ = %s' %subj
    else:
        print ">> STCs for subj=%s:"%subj
        print 'Importing data...'
        info = pickle.load(open('MEG/%s/%s-info.pickled' %(subj,subj), 'rb'))
        epochs_rej = mne.read_epochs('MEG/%s/%s-epo.fif' %(subj,subj))
        trans = mne.read_trans('MEG/%s/%s-trans.fif' %(subj,subj))

        bem_fname = join(subjects_dir, '%s/bem/%s-inner_skull-bem-sol.fif'%(subj,subj))
        src_fname = join(subjects_dir, '%s/bem/%s-ico-4-src.fif' %(subj,subj))
        fwd_fname = 'MEG/%s/%s-fwd.fif' %(subj, subj)
        cov_fname = 'MEG/%s/%s-cov.fif' %(subj,subj)



    #---------------------------get evoked------------------------------------#
        print '%s: Creating evoked responses' %subj
        evoked = []
        conditions = event_id.keys()
        for cond in conditions:
            evoked.append(epochs_rej[cond].average())
        print 'Done.'

        # Sanity check: plot evoked
        if not os.path.isdir('sanity_check/evoked/'):
            os.makedirs('sanity_check/evoked/')
        all_evokeds = mne.combine_evoked(evoked, weights='equal')
        evoked_plot = all_evokeds.plot_joint(show=False)
        evoked_plot.savefig('sanity_check/evoked/%s_evoked.png'%subj)


        #----------------------Source space---------------------------#
        print 'Generating source space...'
        if os.path.isfile(src_fname):
            print 'src for subj = %s already exists, loading file...' %subj
            src = mne.read_source_spaces(fname=src_fname)
            print 'Done.'
        else:
            print 'src for subj = %s does not exist, creating file...' %subj
            src = mne.setup_source_space(subject=subj, spacing='ico4', subjects_dir=subjects_dir)
            src.save(src_fname, overwrite=True)
            print 'Done. File saved.'

        #-------------------------- BEM ------------------------------#
        if not os.path.isfile(bem_fname):
            print 'BEM for subj=%s does not exists, creating...' %subj
            conductivity = (0.3,) # for single layer
            model = mne.make_bem_model(subject=subj, ico=4, conductivity=conductivity, subjects_dir=subjects_dir)
            bem = mne.make_bem_solution(model)
            mne.write_bem_solution(bem_fname, bem)

        #--------------------Forward solution-------------------------#
        print 'Creating forward solution...'
        if os.path.isfile(fwd_fname):
            print 'forward soltion for subj=%s exists, loading file.' %subj
            fwd = mne.read_forward_solution(fwd_fname)
            print 'Done.'
        else:
            print 'forward soltion for subj=%s does not exist, creating file.' %subj
            fwd = mne.make_forward_solution(info=info, trans=trans, src=src, bem=bem_fname, ignore_ref=True)
            mne.write_forward_solution(fwd_fname, fwd)
            print 'Done. File saved.'


        #----------------------Covariance------------------------------#
        print 'Getting covariance'
        if os.path.isfile(cov_fname):
            print 'cov for subj=%s exists, loading file...' %subj
            cov = mne.read_cov(cov_fname)
            print 'Done.'
        else:
            print 'cov for subj=%s does not exist, creating file...' %subj
            cov = mne.compute_covariance(epochs_rej,tmin=None,tmax=0, method=['shrunk', 'diagonal_fixed', 'empirical'])
            cov.save(cov_fname)
            print 'Done. File saved.'


        #---------------------Inverse operator-------------------------#
        print 'Getting inverse operator'
        if fixed == True:
            fwd = mne.convert_forward_solution(fwd, surf_ori=True)

        inv = mne.minimum_norm.make_inverse_operator(info, fwd, cov, depth=None, loose=None, fixed=fixed) #fixed=False: Ignoring dipole direction.
        lambda2 = 1.0 / SNR ** 2.0

        #--------------------------STCs--------------------------------#

        print '%s: Creating STCs...'%subj
        os.makedirs('STC/%s' %subj)
        for ev in evoked:
            stc = mne.minimum_norm.apply_inverse(ev, inv, lambda2=lambda2, method='dSPM')
            # mophing stcs to the fsaverage using precomputed matrix method:
            vertices_to = mne.grade_to_vertices('fsaverage', grade=4, subjects_dir=subjects_dir) #fsaverage's source space
            morph_mat = mne.compute_morph_matrix(subject_from=subj, subject_to='fsaverage', vertices_from=stc.vertices, vertices_to=vertices_to, subjects_dir=subjects_dir)
            stc_morph = mne.morph_data_precomputed(subject_from=subj, subject_to='fsaverage', stc_from=stc, vertices_to=vertices_to, morph_mat=morph_mat)
            stc_morph.save('STC/%s/%s_%s_dSPM' %(subj,subj,ev.comment))
            del stc, stc_morph
        print '>> DONE CREATING STCS FOR SUBJ=%s'%subj
        print '-----------------------------------------\n'

        #deleting variables
        del epochs_rej, evoked, info, trans, src, fwd, cov, inv
