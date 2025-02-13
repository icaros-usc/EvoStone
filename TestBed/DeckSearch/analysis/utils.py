import os
import toml
import json


def read_in_surr_config(log_dir):
    exp_config_file = os.path.join(log_dir, "experiment_config.tml")
    elite_map_config_file = os.path.join(log_dir, "elite_map_config.tml")
    experiment_config = toml.load(exp_config_file)
    elite_map_config = toml.load(elite_map_config_file)
    return experiment_config, elite_map_config


def get_label_color(experiment_config):
    legend = ""
    color = None
    if experiment_config["Search"]["Category"] == "Surrogated":
        # Search algo
        if experiment_config["Search"]["Type"] == "MAP-Elites":
            if experiment_config["Surrogate"]["Type"] == "FullyConnectedNN":
                # legend += "MLP" + " DSM-ME"
                legend += "DSA-ME"
                color = "green"
            elif experiment_config["Surrogate"]["Type"] == "LinearModel":
                legend += "LSA-ME"
                color = "orange"
            elif experiment_config["Surrogate"]["Type"] == "FixedFCNN":
                legend += "Offline DSA-ME"
                fixed_model_path = experiment_config["Surrogate"]["FixedModelSavePath"]
                if fixed_model_path == "resources/fixed_models/miracle_rogue_dsa-me_FCNN_default_target/model.ckpt":
                    legend += " (Surrogate Model)"
                    color = "maroon"
                elif fixed_model_path == "resources/fixed_models/miracle_rogue_dsa-me-offline_FCNN_default_target/model.ckpt":
                    legend += " (Elite Data)"
                    color = "gold"
                elif fixed_model_path in [
                    "resources/fixed_models/miracle_rogue_random_FCNN_default_target/model.ckpt",
                    "resources/fixed_models/miracle_rogue_random_FCNN/model.ckpt"]:
                    # legend += " (Random Data Model)"
                    color = "red"
            else:
                legend += experiment_config["Surrogate"]["Type"] \
                          + " DSA-ME"
                color = None

        # Keep surrogate archive or not
        if experiment_config["Search"].get("KeepSurrogateArchive"):
            legend += " (without resetting)"
            color = "indigo"

    elif experiment_config["Search"]["Category"] == "Distributed":
        legend += experiment_config["Search"]["Type"]
        color = "blue"
    return legend, color


def read_in_paladin_card_index():
    # read in card index
    with open('analysis/paladin_card_index.json') as f:
        card_index = json.load(f)

    card_name = {idx: name for name, idx in card_index.items()}
    return card_index, card_name

def read_in_rogue_card_index():
    # read in card index
    with open('analysis/rogue_card_index.json') as f:
        card_index = json.load(f)

    card_name = {idx: name for name, idx in card_index.items()}
    return card_index, card_name