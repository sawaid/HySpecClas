import os
import re

import gdal
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import (MultipleLocator, FormatStrFormatter,
                               AutoMinorLocator, FixedLocator, LinearLocator)
import h5py
import torch
from nn_test import model
import torch.utils.data
import itertools

system_file = './fsystem_sub_v2.txt'
excel_file = './Classes_names_Hyperspectral 1.xlsx'
class specie:
    def __init__(self, specie):
        self.specie = specie
        self.trees = []

    def add_tree(self, tree):
        if self.specie == tree.specie:
            self.trees.append(tree)


class Tree:
    def __init__(self, ID):
        self.ID = ID

        # find the species by ID
        self.specie = self._find_species_by_ID()

        # find the total Round By ID
        self.tree_images = self._find_tree_images_by_ID()

    def _find_species_by_ID(self):
        lis = open(system_file).readlines()
        for i in lis:
            search_id = re.findall('\_(rtr\d{7})', i, flags=re.I)[0]
            if search_id.upper() == self.ID:
                return re.findall('(.*)\/r\d\/', i, flags=re.I)[0]

    def tree_img_iter(self):
        '''
        Iterator of tree_img for this tree(id)
        '''
        for i in self.tree_images:
            yield i


    def _find_tree_images_by_ID(self):
        lis = open(system_file).readlines()
        pf = pd.read_excel(excel_file, index_col=0)
        re_images = []
        for i in lis:
            search_id = re.findall('\_(rtr\d{7})', i, flags=re.I)[0]
            if search_id.upper() == self.ID:
                rn = re.findall('\/(r\d)\/', i, flags=re.I)[0]
                img_name = i.split('/')[-1][:-5]
                status = pf.loc[img_name, ['Status']].values[0]
                cluster_list_temp = pf.iloc[:, [*tuple(range(4, 10))]].loc[img_name].values
                cluster_list1 = [('Healthy' in i) * 2 for i in cluster_list_temp]
                cluster_list2 = [('Unhealthy' in i) * 1 for i in cluster_list_temp]
                cluster_list = [i+j for i, j in zip(cluster_list1, cluster_list2)]
                cluster_list_BS = [((not 'Saturate'.upper() in i.upper()) and (not 'background'.upper() in i.upper()))
                                 for i in cluster_list_temp]
                print(img_name, cluster_list_BS)
                mean_spectral_without_B_S = None

                # print(rn)
                mean_spectral_file = os.path.join('./all_data', img_name, 'kmeans', 'mean_average.txt')
                cls_file = os.path.join('./all_data', img_name, 'kmeans', 'cls.tif')
                if rn.upper() == 'R5':
                    mean_spectral_file = os.path.join('./R5_data/r5', img_name, 'kmeans', 'mean_average.txt')
                    cls_file = os.path.join('./R5_data/r5', img_name, 'kmeans', 'cls.tif')

                mean_spectral_clusters = np.loadtxt(mean_spectral_file)
                cls_data = gdal.Open(cls_file).ReadAsArray()
                _, cluster_counts = np.unique(cls_data, return_counts=True)
                cluster_counts = cluster_counts[:-1]

                temp = mean_spectral_clusters * np.reshape(cluster_counts, (-1, 1))
                mean_spectral_all_temp = np.sum(temp, axis=0) / np.sum(cluster_counts)

                cluster_counts_BS = cluster_counts[cluster_list_BS]
                mean_spectral_without_B_S = None
                if cluster_counts_BS.size > 0:
                    cluster_counts_BS_temp = temp[cluster_list_BS, :]
                    mean_spectral_without_B_S = np.sum(cluster_counts_BS_temp, axis=0) / np.sum(cluster_counts_BS)

                healthy_counts = cluster_counts[cluster_list == 2]
                mean_spectral_healthy_temp = None
                if healthy_counts.size > 0:
                    healthy_temp = temp[cluster_list == 2, :]
                    mean_spectral_healthy_temp = np.sum(healthy_temp, axis=0) / np.sum(healthy_counts)

                unhealthy_counts = cluster_counts[cluster_list == 1]
                mean_spectral_unhealthy_temp = None
                if unhealthy_counts.size > 0:
                    unhealthy_temp = temp[cluster_list == 1, :]
                    mean_spectral_unhealthy_temp = np.sum(unhealthy_temp, axis=0) / np.sum(unhealthy_counts)
                # cluster_list = [1,0,1,2,0,1],
                # cluster_list_value = ['healthy', 'unhealthy', 'sunlit'....]
                new_tree = tree_image(img_name, rn, status, self.specie,
                                      cluster_counts, cluster_list, cluster_list_BS,
                                      cluster_list_temp, mean_spectral_clusters,
                                      mean_spectral_all_temp, mean_spectral_without_B_S,
                                      mean_spectral_healthy_temp, mean_spectral_unhealthy_temp)

                re_images.append(new_tree)
        return re_images


class tree_image:
    # cluster_list is the list contain files_number that indicte the healthy or unhealthy
    # example: [1, 0, 0, 0, 2, 1], '2' means healthy '1' means unhealthy '2' others
    # mean_spectral_without_B_S without Background and Saturated
    def __init__(self, image_name, rn, status, specie, counts,
                 cluster_list, cluster_list_BS, cluster_list_value, mean_spectral_clusters,
                 mean_spectral_all, mean_spectral_without_B_S,
                 mean_spectral_healthy, mean_spectral_unhealthy):
        self.image_name = image_name
        self.rn = rn
        self.status = status
        self.counts = counts
        self.specie = specie
        self.cluster_list = cluster_list
        self.cluster_list_BS = cluster_list_BS
        self.cluster_list_value = cluster_list_value
        self.mean_spectral_clusters = mean_spectral_clusters
        self.mean_spectral_all = mean_spectral_all
        self.mean_spectral_without_B_S = mean_spectral_without_B_S
        self.mean_spectral_healthy = mean_spectral_healthy
        self.mean_spectral_unhealthy= mean_spectral_unhealthy

colors = np.array([
    (255, 0, 0), # Red
    (143, 188, 143), #DarkSeaGreen
    (255, 105, 180), # Pink
    (147, 112, 219), # Purple
    (0, 255, 0), # Green
    (85, 107, 47), # OliveGreen
    (0, 0, 255), # Blue
    (139, 0, 139), # Magenta
    (184, 134, 11), # GoldenRod
    (178, 34, 34), # FireBrick
    (0, 255, 255), # Aqua
    (165, 42, 42), # Brown
    (255, 228, 196), # Bisque
])

bands = np.load('./bands.npy')
def plot_tree_data(tree):
    graph_name = tree.specie + ' '+ tree.ID
    status_name = ''
    mean_spectral_all = []
    healthy_spectral_all = []
    unhealthy_spectral_all = []
    for tree_img in tree.tree_images:
        basename = tree_img.image_name
        rn = tree_img.rn
        color_index = int(rn[-1])
        status = tree_img.status
        status_name += (rn.upper() + '({})->'.format(status))
        mean_spectral_all.append([tree_img.mean_spectral_all,
                                  colors[color_index, :]/255.,
                                  '{}({})'.format(rn, status)])
        # healthy
        if tree_img.mean_spectral_healthy != None:
            healthy_spectral_all.append([mean_spectral_healthy_temp,
                                         colors[color_index, :]/255.,
                                         '{}({})'.format(rn, status)])
        # unhealthy
        if tree_img.mean_spectral_unhealthy != None:
            unhealthy_spectral_all.append([mean_spectral_unhealthy_temp,
                                           colors[color_index, :]/255.,
                                           '{}({})'.format(rn, status)])

    return (graph_name, status_name[:-2], mean_spectral_all, healthy_spectral_all, unhealthy_spectral_all)

def plot_mean_spectral_round(g_n, s_n, spectral, out_dir):
    for i in spectral:
        plt.plot(bands, i[0], color=i[1], label=i[2].upper())
    plt.xlabel('Wavelength(nm)')
    plt.ylabel('Reflectance')
    plt.title(g_n + '\n' + s_n)
    plt.xlim(380, 1020)
    plt.ylim(0.00, 1)
    plt.yticks(np.arange(0, 1.1, 0.1))
    plt.grid()
    plt.legend(bbox_to_anchor=(1.04, 1), loc="upper left")
    plt.savefig(os.path.join(out_dir, g_n+'.png'), bbox_inches="tight", dpi=300)
    plt.close()

def plot_tree(tree):
    g_n, s_n, spectral, healthy, unhealthy = plot_tree_data(tree)
    plot_mean_spectral_round(g_n, s_n, spectral, './tree')
    # plot all
    if healthy != []:
        plot_mean_spectral_round(g_n + '_Healthy', s_n, healthy, './tree/healthy')

    if unhealthy != []:
        plot_mean_spectral_round(g_n + '_Unhealthy', s_n, unhealthy, './tree/unhealthy')

def plot_tree_img(tree):
    '''
    plot the tree_img for each tree
    '''
    for i in tree.tree_img_iter():
        basename = i.image_name
        # cls_file = os.path.join('./all_data', basename, 'kmeans', 'cls.tif')
        mean_spectral = i.mean_spectral_clusters
        new_figure_file = os.path.join('./all_data', basename, 'kmeans', 'plot_all_new.png')
        legend_names = i.cluster_list_value
        for idx, label_name in enumerate(legend_names):
            plt.plot(bands, mean_spectral[idx, :], color=colors[idx, :]/255., label=label_name)
        plt.xlabel('Wavelength(nm)')
        plt.ylabel('Reflectance')
        plt.title(basename)
        plt.xlim(380, 1020)
        plt.ylim(0.00, 1)
        plt.yticks(np.arange(0, 1.1, 0.1))
        plt.grid()
        plt.legend(bbox_to_anchor=(1.04, 1), loc="upper left")
        plt.savefig(new_figure_file, bbox_inches="tight", dpi=300)
        plt.close()

def cal_indices(S):
    return {
        'HVI': S[117]/S[100],
        'HNDVI': (S[141]-S[94])/(S[141]+S[94]),
        'GI': S[49]/S[97],
        'PRI': (S[45]-S[63])/(S[45]+S[63]),
        'RVSI': 0.5*(S[110]+S[124])-S[114],
        'MCARI': (S[107]*((S[107]-S[97])-0.2*(S[107]-S[49])))/S[97],
        'PRI-2': (S[46]-S[59])/(S[46]+S[59]),
        'NDVI-2': (S[136]-S[96])/(S[136]+S[96]),
        'NDVI': (np.average(S[123:170])-np.average(S[90:123])) /
        (np.average(S[123:170])+np.average(S[90:123])),
        'SAVI': 1.5*(np.average(S[123:170])-np.average(S[90:123])) /
        (np.average(S[123:170])+np.average(S[90:123])+0.5),
        'CIRE': np.average(S[130:170])/np.average(S[100:114]) - 1,
        'CIRE710': S[120]/S[106]-1,
        'CRE': 1/(np.average(S[123:137])/np.average(S[100:111])),
        'NDRE': (np.average(S[130:170])-np.average(S[100:114])) /
        (np.average(S[130:170])+np.average(S[100:114])),
        'NDVIRE': (np.average(S[100:114])-np.average(S[83:124])) /
        (np.average(S[100:114])+np.average(S[83:124])),
        'RE1': np.average(S[106:109])/np.average(S[95:99]),
        'RE2': (np.average(S[106:109])-np.average(S[95:99])) /
        (np.average(S[106:109])+np.average(S[95:99])),
        'REI1': 700+40*((((S[93]-S[130])/2)-S[103])/(S[117]-S[103])),
        'REI2': 700+40*((((S[92]-S[130])/2)-S[104])/(S[117]-S[104])),
        'REI3': 705+35*((((S[91]-S[131])/2)-S[105])/(S[116]-S[105])),
        'REP': 700+40*((((S[93]-S[130])/2)-S[103])/(S[116]-S[103])),
        'PRI1': np.average(S[130:170])/np.average(S[100:114]),
        'PRI2': np.average(S[130:170])/np.average(S[83:124]),
        'VARIRE': (np.average(S[103:107])-np.average(S[76:97])) /
        (np.average(S[103:107])+np.average(S[76:97])),
        'DPI': (S[99]+S[106])/(S[102]*S[102]),
        'FR': (S[100]/S[115]),
        'FR2': (S[100]/S[116]),
        'EVI': 2.5*((np.average(S[130:170])-np.average(S[83:124]))/
        (np.average(S[130:170])+6*(np.average(S[83:124]))-7.5*(np.average(S[8:30])))+1),
        'WDRVI': (0.1*np.average(S[123:170])-np.average(S[90:123]))/
        (0.1*np.average(S[123:170])+np.average(S[90:123])),
        'CIG': np.average(S[130:170])/np.average(S[32:60])-1,
        'ND8068': (S[136]-S[96])/(S[136]+S[96]),
        'MCARI0': (S[103]-S[93]-0.2*(S[103]-S[52]))*(S[103]/S[93]),
        'MCARI1': 1.2*(2.5*(S[136]-S[93])-1.3*(S[136]-S[52])),
        'ND6843': (S[96]-S[11])/(S[96]+S[11]),
        'ND5357': (S[46]-S[59])/(S[46]+S[59]),
        'ND7031': (S[59]-S[46])/(S[59]+S[46]),
        'ND5258': (S[45]-S[65])/(S[45]+S[65]),
        'ND6844': (S[96]-S[15])/(S[96]+S[15]),
        'RDVI': (S[136]-S[93])/np.sqrt(S[136]-S[93]),
        'SRPI': (S[11]/S[96]),
        'SIPI': (S[136]-S[17])/(S[136]-S[96]),
        'TCAR': 3*((S[103]-S[93])-0.2*(S[103]-S[52])*(S[103]/S[93])),
        'TVI': 0.5*(120*(S[120]-S[52])-200*(S[120]-S[52])),
        'MND': (S[114]-S[119])/(S[108]-S[112]),
        'LCI': (S[153]-S[106])/(S[153]+S[96]),
        'DATT1': (S[153]-S[106])/(S[153]-S[96]),
        'DATT2': (S[94])/(S[52]*S[106]),
        'DATT3': (S[156])/(S[52]*S[106]),
        'DDI': (S[120]-S[110])-(S[103]-S[94]),
        'SR6976': (S[101]/S[123]),
        'SR7075': (S[105]/S[120]),
        'SR8060': (S[136]/S[69]),
        'SR8055': (S[136]/S[52]),
        'SR7472': (S[116]/S[110]),
        'SR5567': (S[53]/S[95]),
        'D8068': (S[136]-S[96]),
        'GNDVI': (np.average(S[130:170])-np.average(S[32:60])) /
        (np.average(S[130:170])+np.average(S[32:60])),
        'SB68': S[96],
        'SB635': S[81],
        'SB43': S[11],
        'SB46': S[22],
        'SB64': S[83],
        'SB66': S[90],
        'SB47': S[25],
        'SB55': S[52],
        'SB70': S[104],
        'SB72': S[110],
        'D8055': (S[136]-S[52]),
        'ND7855': (S[150]-S[52])/(S[130]-S[52]),
        'GLI': (2*np.average(S[32:60])-np.average(S[83:124])-np.average(S[8:30]))/
        (2*np.average(S[32:60])+np.average(S[83:124])+np.average(S[8:30]))
    }

def plot_species_rn(specie_dict_ls, species_list_rn):
    out = np.zeros((len(specie_dict_ls), len(species_list_rn), 204))

    for idx, specie in enumerate(specie_dict_ls):
        for idx_rn, species in enumerate(species_list_rn):
            mean_spectral = np.zeros((204))
            count = 0
            for tree in species[specie]:
                if tree.mean_spectral_without_B_S is not None:
                    count += 1
                    mean_spectral += tree.mean_spectral_without_B_S
            mean_spectral /= count
            out[idx, idx_rn, :] = mean_spectral
            plt.plot(bands, mean_spectral, color=colors[idx_rn, :]/255., label='R'+str(idx_rn+1))
        plt.xlabel('Wavelength(nm)')
        plt.ylabel('Reflectance')
        plt.title(specie + '_' +str(idx))
        plt.xlim(380, 1020)
        plt.ylim(0.00, 1)
        plt.yticks(np.arange(0, 1.1, 0.1))
        plt.grid()
        plt.legend(bbox_to_anchor=(1.04, 1), loc="upper left")
        new_figure_file = os.path.join('./trees', 'specie', specie + '.png')
        plt.savefig(new_figure_file, bbox_inches="tight", dpi=300)
        plt.close()
    print(index_species_rn['NDVI'][0][0])
    print(count_temp)
    np.save('./trees/specie/mean_spectral_species', out)


def generate_3D_list(h, w):
    out = []
    for i in range(h):
        out.append([])
        for j in range(w):
            out[i].append([])
    return out

def plot_species_rn_indexes(specie_dict_ls, species_list_rn):
    # index_species_rn = {
    #     'HVI': generate_3D_list(19, 4),
    #     'HNDVI': generate_3D_list(19, 4),
    #     'GI':    generate_3D_list(19, 4),
    #     'PRI':   generate_3D_list(19, 4),
    #     'RVSI':  generate_3D_list(19, 4),
    #     'MCARI': generate_3D_list(19, 4),
    #     'PRI-2':  generate_3D_list(19, 4),
    #     'NDVI-2': generate_3D_list(19, 4),
    #     'NDVI':  generate_3D_list(19, 4),
    #     'SAVI':  generate_3D_list(19, 4)
    # }
    indices_keys = ['HVI', 'HNDVI', 'GI', 'PRI', 'RVSI', 'MCARI', 'PRI-2', 'NDVI-2',
                    'NDVI', 'SAVI', 'CIRE', 'CIRE710', 'CRE', 'NDRE', 'NDVIRE', 'RE1',
                    'RE2', 'REI1', 'REI2', 'REI3', 'REP', 'PRI1', 'PRI2', 'VARIRE', 'DPI',
                    'FR', 'FR2', 'EVI', 'WDRVI', 'CIG', 'ND8068', 'MCARI0', 'MCARI1', 'ND6843',
                    'ND5357', 'ND7031', 'ND5258', 'ND6844', 'RDVI', 'SRPI', 'SIPI', 'TCAR',
                    'TVI', 'MND', 'LCI', 'DATT1', 'DATT2', 'DATT3', 'DDI', 'SR6976', 'SR7075',
                    'SR8060', 'SR8055', 'SR7472', 'SR5567', 'D8068', 'GNDVI', 'SB68', 'SB635',
                    'SB43', 'SB46', 'SB64', 'SB66', 'SB47', 'SB55', 'SB70', 'SB72', 'D8055',
                    'ND7855', 'GLI']
    index_species_rn = {key: generate_3D_list(19, 5) for key in indices_keys}
    count_temp = 0
    outB_fs = open('./trees/indexes/bands_5.txt', 'w')
    out_fs = open('./trees/indexes/indices2_5.txt', 'w')
    for idx, specie in enumerate(specie_dict_ls):
        for idx_rn, species in enumerate(species_list_rn):
            for tree in species[specie]:
                if tree.mean_spectral_without_B_S is not None:
                    indices = cal_indices(tree.mean_spectral_without_B_S)
                    temp_str = specie + ', ' + 'R' + str(idx_rn)
                    tempB_str = specie + ', ' + 'R' + str(idx_rn)
                    temp_str += ', ' + tree.image_name
                    tempB_str += ', ' + tree.image_name
                    for i in tree.mean_spectral_without_B_S:
                        tempB_str += ', ' + '{:.4f}'.format(i)

                    for i in index_species_rn.keys():
                        temp_str += ', ' + '{:.4f}'.format(indices[i])
                        index_species_rn[i][idx][idx_rn].append(indices[i])
                    temp_str += '\n'
                    tempB_str += '\n'
                    out_fs.write(temp_str)
                    outB_fs.write(tempB_str)
    out_fs.close()
    outB_fs.close()
    pass
    # Plot
    specie_ls = np.load('./species.npy')
    specie_ls = specie_ls.tolist()
    for key in index_species_rn.keys():
        test = index_species_rn[key]
        minor_ticks = []
        major_label = []
        major_ticks = []
        mean_all = []
        fig, ax = plt.subplots(figsize=(25, 5))
        minor_label = [str(i+1) for i in range(5)] * 19
        for idx_sp, specie in enumerate(test):
            major_label.append(str(idx_sp) + '_' + specie_ls[idx_sp][:5])
            major_ticks.append(idx_sp * 6)
            for idx_rn, rn in enumerate(specie):
                # print(idx_rn)
                out = idx_sp * 6 + idx_rn + 1
                minor_ticks.append(out)
                x = np.ones((len(rn))) * out
                y = np.array(rn)
                plt.plot(x, y, color=colors[idx_rn, :]/255., linestyle='', marker='x')
                mean_all.append(np.average(y))
        plt.plot(minor_ticks, mean_all, marker='*', linestyle='', color='b')
        plt.grid(b=True, which='major', color='#666666', linestyle='-')
        plt.grid(b=True, which='minor', color='#999999', linestyle='-',
                 linewidth=0.4, alpha=0.5)
        print(major_ticks)
        # temp = ['1']
        # temp.extend(minor_label)
        print(major_label)
        ax.tick_params(axis='x', which='major', pad=10)
        # plt.setp(ax.xaxis.get_majorticklabels(), rotation=-45,
        #          ha="left", rotation_mode="anchor")
        # plt.minorticks_on()
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.xaxis.set_major_locator(MultipleLocator(6))
        ax.set_xticks(major_ticks)
        ax.set_xticks(minor_ticks, minor=True)
        ax.set_xticklabels(major_label, rotation=45)
        ax.set_xticklabels(minor_label, minor=True)
        plt.xlim((0, 114))
        plt.xlabel('Species_Round')
        plt.ylabel('Index_Value')
        plt.title(key)
        plt.savefig(os.path.join('./trees/indexes', key+'.png'),
                    bbox_inches='tight', dpi=300)

if __name__ == '__main__2':
    tree_ls = [Tree(i) for i in np.load('./tree_id.npy')]
    specie_dict_ls = {i:[] for i in np.load('./species.npy')}
    [specie_dict_ls[i.specie].append(i) for i in tree_ls]


if __name__ == '__main__2':
    tree_ls = [Tree(i) for i in np.load('./tree_id.npy')]
    specie_dict_ls = {i:[] for i in np.load('./species.npy')}
    [specie_dict_ls[i.specie].append(i) for i in tree_ls]
    # print(specie_dict_ls)
    specie = []
    rn_list = range(5)
    # for round 5
    # rn_list = [4]
    for rn in rn_list:
        specie_rn = {}
        for i in specie_dict_ls:
            specie_rn[i] = []
            for j in specie_dict_ls[i]:
                for k in j.tree_images:
                    if k.rn.upper() == ('R' + str(rn + 1)):
                        specie_rn[i].append(k)
        specie.append(specie_rn)
    plot_species_rn_indexes(specie_dict_ls, specie)
    # # print([len(specie_r1[i]) for i in specie_r1])
    # tree_species = [i.specie for i in tree_ls]
    # np.save('./species.npy', np.unique(np.array(tree_species)))
    # print(np.unique(np.array(tree_species)))
def plotBVB():
    image_names = ['REFLECTANCE_2019-06-10_016', 'REFLECTANCE_2019-06-10_035']
    for img_name in image_names:
        cls_file = os.path.join('./sawaid_scatters', img_name + '_cls.tif')
        spectral_file = os.path.join('./sawaid_scatters', img_name + '.tif')
        cls_data = gdal.Open(cls_file).ReadAsArray()
        spectral_data = gdal.Open(spectral_file).ReadAsArray()
        spectral_data = np.transpose(spectral_data, (1, 2, 0))
        cluster_indexes = np.arange(6)
        for i in cluster_indexes:
            b125 = spectral_data[cls_data==i, 124]
            b101 = spectral_data[cls_data==i, 100]
            plt.plot(b125, b101,color=colors[i, :]/255,
                     label='Cluster'+str(i), linestyle='', marker='x', alpha=0.7)
        plt.legend()
        plt.xlabel('B125')
        plt.ylabel('B101')
        plt.title(img_name)
        plt.savefig(os.path.join('./sawaid_scatters', img_name+'.png'), bbox_inches='tight', dpi=300)
        plt.close()

        for i in cluster_indexes:
            S = spectral_data[cls_data==i, :]
            PRI = (S[:, 45]-S[:, 63])/(S[:, 45]+S[:, 63])
            NDVI = (np.average(S[:, 123:170], axis=1)-np.average(S[:, 90:123], axis=1)) / (np.average(S[:, 123:170], axis=1)+np.average(S[:, 90:123], axis=1))
            plt.plot(NDVI, PRI, color=colors[i, :]/255,
                     label='Cluster'+str(i), linestyle='', marker='x', alpha=0.7)
        plt.legend()
        plt.xlabel('NDVI')
        plt.ylabel('PRI')
        plt.title(img_name)
        plt.savefig(os.path.join('./sawaid_scatters', img_name+'_ind.png'), bbox_inches='tight', dpi=300)
        plt.close()

# generate HDF files
if __name__ == '__main__2':
    tree_ls = [Tree(i) for i in np.load('./tree_id.npy')]
    specie_dict_ls = {i:[] for i in np.load('./species.npy')}
    [specie_dict_ls[i.specie].append(i) for i in tree_ls]
    # print(specie_dict_ls)
    specie = []
    for rn in range(4, 5):
        specie_rn = {}
        for i in specie_dict_ls:
            specie_rn[i] = []
            for j in specie_dict_ls[i]:
                for k in j.tree_images:
                    if k.rn.upper() == ('R' + str(rn + 1)):
                        specie_rn[i].append(k)
        specie.append(specie_rn)

    # [plot_tree(i) for i in tree_ls]
    # [plot_tree_img(i) for i in tree_ls]
    fs = open('./fsystem_sub_v2.txt', 'r').readlines()
    spectral_dir = '/home/kevin/temp/temp'
    for r_idex, r in enumerate(specie):
        print(r_idex)
        h5f = h5py.File('./nn_test/dataset/train_' + str(r_idex+5) + '.h5', 'w')
        g_train = h5f.create_group('train')
        g_val = h5f.create_group('val')
        train_data_ds = g_train.create_dataset('features', (0, 204), maxshape=(None, 204),
                                    compression=None, dtype='f')
        train_label_ds = g_train.create_dataset('labels', shape=(0,), maxshape=(None,),
                                    compression=None, dtype='int32')

        val_data_ds = g_val.create_dataset('features', (0, 204), maxshape=(None, 204),
                                    compression=None, dtype='f')
        val_label_ds = g_val.create_dataset('labels', shape=(0,), maxshape=(None,),
                                    compression=None, dtype='int32')
        # h5f = h5
        temp_count = 0
        for label_idx, spc in enumerate(r.keys()):
            for tree in r[spc]:
                # find the spectral file path
                temp = np.arange(6)
                value = temp[np.array(tree.cluster_list)>0]
                file_path = ''
                cls_file = os.path.join('./R5_data/r5', tree.image_name, 'kmeans', 'cls.tif')
                for temp_path in fs:
                    if tree.image_name in temp_path:
                        file_path = temp_path[:-1]
                        break
                spectral_file = os.path.join(spectral_dir, file_path)
                cls_data = gdal.Open(cls_file).ReadAsArray()
                spectral_data = gdal.Open(spectral_file).ReadAsArray()
                spectral_data = np.transpose(spectral_data, (1, 2, 0))
                for i in value:
                    data = spectral_data[cls_data==i, :]
                    num_lines, _ = data.shape
                    label = np.ones((num_lines,)) * label_idx
                    flagInt = np.random.randint(1, 11, (num_lines,))
                    # num lines for train
                    n_l_for_train = np.sum(flagInt%5!=0)
                    n_l_for_val = num_lines - n_l_for_train
                    # data_for_train = data[flagInt%5!=0, :]
                    # label_for_train = data[flagInt%5!=0, :]

                    # for train
                    train_data_ds.resize(train_data_ds.shape[0]+n_l_for_train, axis=0)
                    train_label_ds.resize(train_label_ds.shape[0]+n_l_for_train, axis=0)
                    train_data_ds[-n_l_for_train:, :] = data[flagInt%5!=0, :].astype('float32')
                    train_label_ds[-n_l_for_train:] = label[flagInt%5!=0].astype('int32')
                    # for val
                    val_data_ds.resize(val_data_ds.shape[0]+n_l_for_val, axis=0)
                    val_label_ds.resize(val_label_ds.shape[0]+n_l_for_val, axis=0)
                    val_data_ds[-n_l_for_val:, :] = data[flagInt%5==0, :].astype('float32')
                    val_label_ds[-n_l_for_val:] = label[flagInt%5==0].astype('int32')
                    temp_count += tree.counts[i]
        print(temp_count)
        h5f.close()

class testDataset(torch.utils.data.Dataset):
    def __init__(self, data):
        self.length, _ = data.shape
        self.data = data
    def __len__(self):
        return self.length
    def __getitem__(self, idx):
        x = torch.tensor(self.data[idx, :])
        return x


def dlm(flag, round_num, specie_dict_ls):
    # flag = 1234
    # round_num = 5
    cls_file_dir = './R5_data/r5' if round_num == 5 else './all_data'
    # tree_imgs for round 1
    r1 = []
    for i in specie_dict_ls:
        for j in specie_dict_ls[i]:
            for k in j.tree_images:
                if k.rn.upper() == ('R' + str(round_num)):
                    r1.append(k)
    print(len(r1))
    fs = open('./system_v2.txt', 'r').readlines()
    spectral_dir = '/home/kevin/temp/temp'

    tree_count = 0
    tree_count_top3 = 0
    tree_count_plot = 0
    tree_count_top3_plot = 0
    tree_txt_file = './nn_test/tree_model{}_pred{}.txt'.format(flag, round_num)
    tree_txt_fs = open(tree_txt_file, 'w')
    tree_plot_txt_file = './nn_test/tree_plot_model{}_pred{}.txt'.format(flag, round_num)
    tree_plot_txt_fs = open(tree_plot_txt_file, 'w')
    for tree in r1:
        cls_file = os.path.join(cls_file_dir, tree.image_name, 'kmeans', 'cls.tif')
        for temp_path in fs:
            if tree.image_name in temp_path:
                file_path = temp_path[:-1]
                break
        spectral_file = os.path.join(spectral_dir, file_path)
        cls_data = gdal.Open(cls_file).ReadAsArray()
        spectral_data = gdal.Open(spectral_file.replace('Results', 'results')).ReadAsArray()
        spectral_data = np.transpose(spectral_data, (1, 2, 0))
        spectral_data_1D = spectral_data.reshape((512*512, 204))
        r_ind = np.random.randint(1, 11, (512*512, ))
        train_data = spectral_data_1D[r_ind % 10 == 0, :]
        p_counts, _ = train_data.shape
        # make plot area
        spectral_data_plot = spectral_data[cls_data<255, :]
        r_ind_2 = np.random.randint(1, 6, (spectral_data_plot.shape[0], ))
        train_data_2 = spectral_data_plot[r_ind_2 % 2 == 0, :]

        p_counts_2, _ = train_data_2.shape
        train_ds = testDataset(train_data)
        train_ds_load = torch.utils.data.DataLoader(train_ds, batch_size=1000,
                                                    shuffle=False, num_workers=0)

        train_ds_2 = testDataset(train_data_2)
        train_ds_load_2 = torch.utils.data.DataLoader(train_ds_2, batch_size=1000,
                                                    shuffle=False, num_workers=0)

        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        model_ft = model.Net(204, 19)
        model_ft = model_ft.to(device)
        model_ft.load_state_dict(torch.load('./nn_test/checkpoints/ck{}.pth'.format(flag), map_location=device))
        model_ft.eval()
        # for all
        re_pred = []
        with torch.no_grad():
            for i, inputs in enumerate(train_ds_load):
                inputs = inputs.to(device)
                outputs = model_ft(inputs)
                _, preds = torch.max(outputs, 1)
                # print(outputs, preds)
                re_pred.extend(preds.view(-1).tolist())
        out, counts = np.unique(np.array(re_pred), return_counts=True)
        pred_tree = out[np.argmax(counts)]
        print(species[pred_tree], ' | ',tree.specie, ' | ', np.max(counts)/np.float(p_counts))
        tree_txt_fs.write(species[pred_tree]+
                          ' | '+tree.specie+ ' | '+
                          '{:.2f}\n'.format(np.max(counts)/np.float(p_counts)))
        pred_tree_top3 = out[np.argsort(counts)[-3:]]
        if tree.specie.upper() in [i.upper() for i in species[pred_tree_top3]]:
            tree_count_top3 += 1
        if species[pred_tree].upper() == tree.specie.upper():
            tree_count += 1
        # for plot
        re_pred = []
        with torch.no_grad():
            for i, inputs in enumerate(train_ds_load_2):
                inputs = inputs.to(device)
                outputs = model_ft(inputs)
                _, preds = torch.max(outputs, 1)
                # print(outputs, preds)
                re_pred.extend(preds.view(-1).tolist())
        out, counts = np.unique(np.array(re_pred), return_counts=True)
        pred_tree = out[np.argmax(counts)]
        print(species[pred_tree],' | ', tree.specie,' | ', np.max(counts)/np.float(p_counts_2))
        tree_plot_txt_fs.write(species[pred_tree]+
                               ' | '+tree.specie+ ' | '+
                               '{:.3f}\n'.format(np.max(counts)/np.float(p_counts_2)))
        pred_tree_top3 = out[np.argsort(counts)[-3:]]
        if tree.specie.upper() in [i.upper() for i in species[pred_tree_top3]]:
            tree_count_top3_plot += 1
        if species[pred_tree].upper() == tree.specie.upper():
            tree_count_plot += 1
        print('')
    tree_txt_fs.close()
    tree_plot_txt_fs.close()
    print(tree_count, tree_count_top3, tree_count_plot, tree_count_top3_plot, len(r1))
    return '{:.3f}\t{:.3f}\t{}\t{}\t{}\n'.format(float(tree_count)/len(r1),
                                                float(tree_count_plot)/len(r1),
                                                tree_count,
                                                tree_count_plot,
                                                len(r1))
##### Deep learning
if __name__ == '__main__':
    flag_list = [1,2,3,4,5,13,24,35,1234]
    round_num_list = [1,2,3,4,5]
    # flag_list = [13, 35]
    # round_num_list = [5]

    tree_ls = [Tree(i) for i in np.load('./tree_id.npy')]
    specie_dict_ls = {i:[] for i in np.load('./species.npy')}
    species = np.load('./species.npy')
    [specie_dict_ls[i.specie].append(i) for i in tree_ls]

    re_fs = open('./nn_test/all_acc.txt', 'w')
    for i, j in itertools.product(flag_list, round_num_list):
        print(i, ' r', j)
        out = dlm(i, j, specie_dict_ls)
        re_fs.write(str(i) + ' R' + str(j) + ' ' + out)
    re_fs.close()