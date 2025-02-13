import argparse
import os
import csv
import numpy as np
import seaborn as sns
import pandas as pd
import scipy.stats as st
import matplotlib.pyplot as plt
import warnings
from matplotlib.ticker import MaxNLocator, MultipleLocator
from matplotlib import rc
from matplotlib.lines import Line2D
from pprint import pprint
from tqdm import tqdm
from utils import get_label_color, read_in_surr_config
from joblib import Parallel, delayed

# turn off runtime warning
warnings.filterwarnings("ignore", category=RuntimeWarning)

# set matplotlib params
plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "serif",
    "font.serif": ["Palatino"],
    "axes.unicode_minus": False,
})

NUM_FEATURES = 2
NUM_EVAL = 20000
NUM_GAME = 200
FITNESS_MIN = -30
FITNESS_MAX = 30
PLOT_OUT_OF_DIST_LOSS = False
OUT_OF_DIST_LABELS = {
    "Sum test out-of-dist loss": "Total Loss",
    "AverageHealthDifference test out-of-dist loss": "Loss on Objective",
    "NumTurns test out-of-dist loss": "Loss on measure 1 (Num Turns)",
    "HandSize test out-of-dist loss": "Loss on measure 2 (Hand Size)"
}
SPLIT_MODE = "split"
COMBINE_MODE = "combine"


def get_fitness_from_cell(cell_data):
    splitedData = cell_data.split(":")
    nonFeatureIdx = NUM_FEATURES
    fitness = float(splitedData[nonFeatureIdx + 3])
    return fitness


def get_win_cnt_from_cell(cell_data):
    splitedData = cell_data.split(":")
    nonFeatureIdx = NUM_FEATURES
    win = int(splitedData[nonFeatureIdx + 2])
    return win


def calculate_stats(log_dir, experiment_config, elite_map_config):
    log_file = os.path.join(log_dir, "elite_map_log.csv")

    # read in resolutions of elite map
    total_num_cell = np.power(elite_map_config["Map"]["StartSize"], 2)

    with open(log_file, "r") as csvfile:
        rowData = list(csv.reader(csvfile, delimiter=','))[1:NUM_EVAL + 1]
        assert len(rowData) == NUM_EVAL
        qd_scores = []
        num_elites = []
        for mapData in rowData:
            # get number of elites
            num_elites.append(len(mapData[1:]))

            # get qd score
            qd_score = 0
            max_fitness = -np.inf
            max_win = -np.inf
            for cellData in mapData[1:]:
                fitness = get_fitness_from_cell(cellData)
                win = get_win_cnt_from_cell(cellData)
                # normalize fitness to [0, 1]
                fitness_nor = (fitness - FITNESS_MIN) \
                            / (FITNESS_MAX - FITNESS_MIN)
                qd_score += fitness_nor
                if fitness > max_fitness:
                    max_fitness = fitness
                if win > max_win:
                    max_win = win
            qd_scores.append(qd_score)

        max_winrate = max_win / NUM_GAME * 100
        cell_filled = len(rowData[-1]) / total_num_cell * 100
        last_qd_score = qd_score

        # get ccdf count from the last map
        curr_last_fitnesses = []
        for cellData in rowData[-1][1:]:
            fitness = get_fitness_from_cell(cellData)
            curr_last_fitnesses.append(fitness)

        percent_elites_ccdf = []
        curr_last_fitnesses = np.asarray(curr_last_fitnesses)
        for fitness in range(FITNESS_MIN, FITNESS_MAX + 1):
            percent_elites_ccdf.append(
                (curr_last_fitnesses > fitness).sum() / total_num_cell * 100)

    loss_log_file = os.path.join(log_dir, "surrogate_train_log",
                                 "model_losses.csv")

    out_of_dist_losses = None

    if os.path.exists(loss_log_file) and PLOT_OUT_OF_DIST_LOSS:
        losses_pd = pd.read_csv(loss_log_file)
        out_of_dist_losses = losses_pd[OUT_OF_DIST_LABELS.keys()]
        # if "Sum test out-of-dist loss" in losses_pd.columns:
        #     out_of_dist_losses = losses_pd["Sum test out-of-dist loss"]

    return (num_elites, qd_scores, last_qd_score, max_fitness, max_winrate,
            cell_filled, curr_last_fitnesses, percent_elites_ccdf,
            out_of_dist_losses)


def process_out_of_dist_losses(all_out_of_dist_losses):
    for label, curr_losses in all_out_of_dist_losses.items():
        min_epoch_num = np.inf
        for out_of_dist_loss in curr_losses:
            if len(out_of_dist_loss) < min_epoch_num:
                min_epoch_num = len(out_of_dist_loss)

        for i in range(len(curr_losses)):
            all_out_of_dist_losses[label][i] = all_out_of_dist_losses[label][
                i][:min_epoch_num]

    return all_out_of_dist_losses


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l',
        '--log_dir_plot',
        help='Dir that contains log dirs to plot.',
        # nargs='+',
        required=True,
    )
    parser.add_argument(
        '-a',
        '--add_legend',
        required=False,
        help="whether add legend to the plot",
        action='store_true',
    )
    parser.add_argument(
        '-ol',
        '--out_of_dist_loss',
        required=False,
        help="whether to plot out-of-dist loss",
        action='store_true',
    )
    parser.add_argument(
        '-m',
        '--mode',
        required=False,
        help=
        "Mode of plotting. 'combine' would combine all plots. 'split' would generate plots separately.",
        default=COMBINE_MODE)

    opt = parser.parse_args()
    log_dir_plot = opt.log_dir_plot
    add_legend = opt.add_legend
    mode = opt.mode
    if mode not in {COMBINE_MODE, SPLIT_MODE}:
        raise ValueError(f"Plotting mode {mode} does not exist.")
    PLOT_OUT_OF_DIST_LOSS = opt.out_of_dist_loss

    qdplots = {}
    for log_dir in os.listdir(log_dir_plot):
        # read in the name of the algorithm and features to plot
        log_dir = os.path.join(log_dir_plot, log_dir)
        if os.path.isdir(log_dir):
            experiment_config, elite_map_config = read_in_surr_config(log_dir)
            curr_exp_id = experiment_config["Search"]["Category"] + "_" + \
                        experiment_config["Search"]["Type"]
            if "Surrogate" in experiment_config:
                surrogate_type = experiment_config["Surrogate"]["Type"]
                curr_exp_id += "_" + surrogate_type
                if surrogate_type == "FixedFCNN":
                    curr_exp_id += "_" + experiment_config["Surrogate"][
                        "FixedModelSavePath"]
                if experiment_config["Search"].get("KeepSurrogateArchive"):
                    curr_exp_id += "_KeepSurrogateArchive"

            # add to dict
            if curr_exp_id in qdplots:
                qdplots[curr_exp_id].append(
                    (log_dir, experiment_config, elite_map_config))
            else:
                qdplots[curr_exp_id] = [(log_dir, experiment_config,
                                         elite_map_config)]

    # plot QD score of surrogate searchs alltogether
    image_title = "Emulation-ME & MAP-Elites"
    legends = []

    numerical_measures = {}
    avg_numerical_measures = {
        "algo": [],
        "max_fitness": [],
        "max_winrate": [],
        "cell_filled": [],
        "qd_score": [],
    }
    sem_numerical_measures = {
        "algo": [],
        "max_fitness": [],
        "max_winrate": [],
        "cell_filled": [],
        "qd_score": [],
    }
    elites_dists = {
        "legends": [],
        "fitnesses": [],
    }

    if mode == SPLIT_MODE:
        qd_fig, qd_ax = plt.subplots(figsize=(8, 6))
        num_elites_fig, num_elites_ax = plt.subplots(figsize=(8, 6))
        ccdf_fig, ccdf_ax = plt.subplots(figsize=(8, 6))
    elif mode == COMBINE_MODE:
        fig, (qd_ax, num_elites_ax, ccdf_ax) = \
            plt.subplots(1, 3, figsize=(33, 6))

    out_of_dist_fig, out_of_dist_ax = plt.subplots(figsize=(8, 5))

    for curr_plots in tqdm(qdplots.values()):
        # take average of current type of algo
        all_num_elites = []
        all_qd_scores = []
        all_last_qd_score = []
        all_max_fitness = []
        all_cell_filled = []
        all_percent_ccdf = []
        all_last_fitness = []
        all_max_winrate = []
        all_out_of_dist_losses = {}  # out-of-dist losses have many dimensions

        results = Parallel(n_jobs=8)(
            delayed(calculate_stats)(log_dir, experiment_config,
                                     elite_map_config)
            for log_dir, experiment_config, elite_map_config in curr_plots)

        algo_label, color = get_label_color(curr_plots[0][1])
        # if algo_label != "MAP-Elites":
        #     algo_label += " (with/without Ancillary Data)"
        numerical_measures[algo_label] = {}

        for result in results:
            (num_elites, qd_scores, qd_score, max_fitness, max_winrate,
             cell_filled, curr_last_fitnesses, percent_elites_ccdf,
             out_of_dist_losses) = result
            all_num_elites.append(num_elites)
            all_qd_scores.append(qd_scores)
            all_last_qd_score.append(qd_score)
            all_max_fitness.append(max_fitness)
            all_max_winrate.append(max_winrate)
            all_cell_filled.append(cell_filled)
            all_last_fitness.append(curr_last_fitnesses)
            all_percent_ccdf.append(percent_elites_ccdf)
            if out_of_dist_losses is not None:
                # PLOT_OUT_OF_DIST_LOSS = True
                for label in out_of_dist_losses:
                    if label in all_out_of_dist_losses:
                        all_out_of_dist_losses[label].append(
                            out_of_dist_losses[label])
                    else:
                        all_out_of_dist_losses[label] = [
                            out_of_dist_losses[label]
                        ]
                    # all_out_of_dist_losses.append(out_of_dist_losses)

        # get average and std
        avg_qd_scores = np.mean(np.array(all_qd_scores), axis=0)
        avg_num_elites = np.mean(np.array(all_num_elites), axis=0)
        avg_percent_ccdf = np.mean(np.array(all_percent_ccdf), axis=0)
        std_qd_scores = np.std(np.array(all_qd_scores), axis=0)
        std_num_elites = np.std(np.array(all_num_elites), axis=0)
        std_num_ccdf = np.std(np.array(all_percent_ccdf), axis=0)
        cf_qd_scores = st.t.interval(alpha=0.95,
                                     df=len(all_qd_scores) - 1,
                                     loc=avg_qd_scores,
                                     scale=st.sem(all_qd_scores))
        cf_num_elites = st.t.interval(alpha=0.95,
                                      df=len(all_num_elites) - 1,
                                      loc=avg_num_elites,
                                      scale=st.sem(all_num_elites))
        cf_percent_ccdf = st.t.interval(alpha=0.95,
                                        df=len(all_percent_ccdf) - 1,
                                        loc=avg_percent_ccdf,
                                        scale=st.sem(all_percent_ccdf))

        # plot out-of-dist losses, if any
        if PLOT_OUT_OF_DIST_LOSS:
            all_out_of_dist_losses = process_out_of_dist_losses(
                all_out_of_dist_losses)
            for label, out_of_dist_losses in all_out_of_dist_losses.items():
                avg_out_of_dist_losses = np.mean(np.array(out_of_dist_losses),
                                                 axis=0)
                cf_out_of_dist_losses = st.t.interval(
                    alpha=0.95,
                    df=len(out_of_dist_losses) - 1,
                    loc=avg_out_of_dist_losses,
                    scale=st.sem(out_of_dist_losses))
                p = out_of_dist_ax.plot(avg_out_of_dist_losses,
                                        label=OUT_OF_DIST_LABELS[label],
                                        color=None)
                out_of_dist_ax.fill_between(np.arange(
                    len(avg_out_of_dist_losses)),
                                            cf_out_of_dist_losses[1],
                                            cf_out_of_dist_losses[0],
                                            alpha=0.5,
                                            color=p[0].get_color())

        avg_numerical_measures["algo"].append(algo_label)
        avg_numerical_measures["qd_score"].append(np.mean(all_last_qd_score))
        avg_numerical_measures["max_fitness"].append(np.mean(all_max_fitness))
        avg_numerical_measures["cell_filled"].append(np.mean(all_cell_filled))
        avg_numerical_measures["max_winrate"].append(np.mean(all_max_winrate))
        sem_numerical_measures["algo"].append(algo_label)
        sem_numerical_measures["qd_score"].append(st.sem(all_last_qd_score))
        sem_numerical_measures["max_fitness"].append(st.sem(all_max_fitness))
        sem_numerical_measures["cell_filled"].append(st.sem(all_cell_filled))
        sem_numerical_measures["max_winrate"].append(st.sem(all_max_winrate))
        numerical_measures[algo_label]["qd_score"] = all_last_qd_score
        numerical_measures[algo_label]["max_fitness"] = all_max_fitness
        numerical_measures[algo_label]["cell_filled"] = all_cell_filled
        numerical_measures[algo_label]["max_winrate"] = all_max_winrate

        # plot qd score
        qd_p = qd_ax.plot(avg_qd_scores, label=algo_label, color=color)
        qd_ax.fill_between(
            np.arange(len(avg_qd_scores)),
            cf_qd_scores[1],
            cf_qd_scores[0],
            alpha=0.5,
            color=color,
        )

        # plot num elites
        num_elites_ax.plot(avg_num_elites, label=algo_label, color=color)
        num_elites_ax.fill_between(
            np.arange(len(avg_num_elites)),
            cf_num_elites[1],
            cf_num_elites[0],
            alpha=0.5,
            color=color,
        )

        # plot CCDF
        ccdf_ax.plot(np.arange(FITNESS_MIN, FITNESS_MAX + 1),
                     avg_percent_ccdf,
                     label=algo_label,
                     color=color)
        ccdf_ax.fill_between(
            np.arange(FITNESS_MIN, FITNESS_MAX + 1),
            cf_percent_ccdf[1],
            cf_percent_ccdf[0],
            alpha=0.5,
            color=color,
        )

    label_fontsize = 35
    tick_fontsize = 30

    # finalize qd score plot
    # qd_ax.legend(loc='lower left',
    #              fontsize='x-large',
    #              bbox_to_anchor=(0, 1.02, 1, 0.2),
    #              borderaxespad=0,
    #              ncol=2,
    #              mode="expand")
    qd_ax.set_xlabel('Evaluations', fontsize=label_fontsize)
    qd_ax.set_ylabel('QD-score', fontsize=label_fontsize)
    qd_ax.set(xlim=(0, NUM_EVAL), ylim=(0, 400))
    qd_ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=2))
    qd_ax.yaxis.set_major_locator(MaxNLocator(integer=False, nbins=2))
    qd_ax.tick_params(labelsize=tick_fontsize)
    # qd_fig.savefig(os.path.join(log_dir_plot, image_title + " QD-score.pdf"),
    #                bbox_inches="tight")

    # finalize num elites plot
    # num_elites_ax.legend(loc='lower left',
    #                      fontsize='x-large',
    #                      bbox_to_anchor=(0, 1.02, 1, 0.2),
    #                      borderaxespad=0,
    #                      ncol=2,
    #                      mode="expand")
    num_elites_ax.set_xlabel('Evaluations', fontsize=label_fontsize)
    num_elites_ax.set_ylabel('Number of Elites', fontsize=label_fontsize)
    num_elites_ax.set(xlim=(0, NUM_EVAL), ylim=(0, 600))
    num_elites_ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=2))
    num_elites_ax.yaxis.set_major_locator(MaxNLocator(integer=False, nbins=2))
    num_elites_ax.tick_params(labelsize=tick_fontsize)
    # num_elites_fig.savefig(os.path.join(log_dir_plot,
    #                                     image_title + " Num elites.pdf"),
    #                        bbox_inches="tight")

    # finalize ccdf plot
    # ccdf_ax.legend(facecolor='white',
    #                loc='lower left',
    #                fontsize='x-large',
    #                bbox_to_anchor=(0, 1.02, 1, 0.2),
    #                borderaxespad=0,
    #                ncol=2,
    #                mode="expand")
    ccdf_ax.set_xlabel('Average Health Difference', fontsize=label_fontsize)
    ccdf_ax.set_ylabel('Threshold Percentage', fontsize=label_fontsize)
    ccdf_ax.set(xlim=(FITNESS_MIN, FITNESS_MAX), ylim=(0, 40))
    ccdf_ax.xaxis.set_major_locator(MaxNLocator(integer=False, nbins=2))
    ccdf_ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=2))
    ccdf_ax.tick_params(labelsize=tick_fontsize)
    # ccdf_fig.savefig(os.path.join(log_dir_plot, image_title + " CCDF.pdf"),
    #                  bbox_inches="tight")

    if add_legend:
        if mode == COMBINE_MODE:
            handles, labels = ccdf_ax.get_legend_handles_labels()

            # if "more_target" in log_dir_plot:
            #     # add legend for LSA-ME
            #     lsa_me_line = Line2D([0], [0],
            #                          color='orange',
            #                          lw=1,
            #                          label='LSA-ME')
            #     handles.append(lsa_me_line)
            #     labels.append("LSA-ME")

            fig.legend(
                handles,
                labels,
                loc="lower center",
                ncol=4,
                fontsize=32,
                #    mode="expand",
                bbox_to_anchor=(0.5, -0.3), # for ncols=4
                # bbox_to_anchor=(0.5, -0.4),  # for ncols=2
                # borderaxespad=0,
            )

        elif mode == SPLIT_MODE:
            qd_ax.legend(loc='lower left',
                         fontsize='x-large',
                         bbox_to_anchor=(0, 1.02, 1, 0.2),
                         borderaxespad=0,
                         ncol=2,
                         mode="expand")
            num_elites_ax.legend(loc='lower left',
                                 fontsize='x-large',
                                 bbox_to_anchor=(0, 1.02, 1, 0.2),
                                 borderaxespad=0,
                                 ncol=2,
                                 mode="expand")
            ccdf_ax.legend(facecolor='white',
                           loc='lower left',
                           fontsize='x-large',
                           bbox_to_anchor=(0, 1.02, 1, 0.2),
                           borderaxespad=0,
                           ncol=2,
                           mode="expand")

        if PLOT_OUT_OF_DIST_LOSS:
            handles, labels = out_of_dist_ax.get_legend_handles_labels()

            out_of_dist_fig.legend(
                handles,
                labels,
                loc="lower center",
                ncol=2,
                fontsize=25,
                #    mode="expand",
                bbox_to_anchor=(0.5, -0.5),  # for ncols=2
                # borderaxespad=0,
            )

    if PLOT_OUT_OF_DIST_LOSS:
        out_of_dist_ax.set_xlabel('Training Epoches', fontsize=label_fontsize)
        out_of_dist_ax.set_ylabel('Validation MSE Loss',
                                  fontsize=label_fontsize)
        out_of_dist_ax.set(xlim=(0, None), ylim=(0, 50))
        out_of_dist_ax.xaxis.set_major_locator(
            MaxNLocator(integer=False, nbins=5))
        out_of_dist_ax.yaxis.set_major_locator(
            MaxNLocator(integer=True, nbins=2))
        out_of_dist_ax.tick_params(labelsize=tick_fontsize)
        out_of_dist_fig.savefig(os.path.join(log_dir_plot,
                                             f"Validation Loss.pdf"),
                                bbox_inches="tight")

    if mode == COMBINE_MODE:
        # add row label
        if "more_target" in log_dir_plot:
            row_label = "With Ancillary Data"
        else:
            row_label = "Without Ancillary Data"

        # fig.suptitle("Post-hoc Experiments", y=1.02, fontsize=40)
        # fig.suptitle(row_label, y=1.02, fontsize=40)
        fig.savefig(os.path.join(log_dir_plot, f"{image_title}.pdf"),
                    bbox_inches="tight")
    elif mode == SPLIT_MODE:
        qd_fig.savefig(os.path.join(log_dir_plot,
                                    image_title + " QD-score.png"),
                       bbox_inches="tight")
        num_elites_fig.savefig(os.path.join(log_dir_plot,
                                            image_title + " Num elites.pdf"),
                               bbox_inches="tight")
        ccdf_fig.savefig(os.path.join(log_dir_plot, image_title + " CCDF.pdf"),
                         bbox_inches="tight")

    # write numerical results
    numerical_measures_df = pd.DataFrame(numerical_measures)
    numerical_measures_df.to_csv(
        os.path.join(log_dir_plot, "numerical_measures.csv"))

    avg_numerical_measures_df = pd.DataFrame(avg_numerical_measures)
    avg_numerical_measures_df.to_csv(
        os.path.join(log_dir_plot, "avg_numerical_measures.csv"))

    sem_numerical_measures_df = pd.DataFrame(sem_numerical_measures)
    sem_numerical_measures_df.to_csv(
        os.path.join(log_dir_plot, "sem_numerical_measures.csv"))
