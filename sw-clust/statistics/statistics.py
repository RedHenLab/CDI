# Provide the statistics for SW Process
import sys
sys.path.append('..')

import mpmath

from model import probability


class Statistics(object):
    def __init__(self, nodes, cnum, np1voc, vpvoc, np2voc, np1prob, vpprob, np2prob, classpriorprob, transprob, length_prior):
        self.all_nodes = nodes
        self.class_num = cnum
        self.np1_voc = np1voc
        self.np1_prob = np1prob
        self.vp_voc = vpvoc
        self.vp_prob = vpprob
        self.np2_voc = np2voc
        self.np2_prob = np2prob
        self.transition_prob = transprob
        self.class_prior = classpriorprob
        self.length_prior = length_prior

    def calculate_Qe(self, left, right, context):
        right_node = self.all_nodes.nodes[right]
        if right_node.pronoun:  # If the beginning of the right node is pronoun, turn on the edge
            return 1
        else:  # Return the probability
            count = int(context.iteration_counter/100)
            if count > 7:
                count = 7
            return 0.2 + 0.1*count

    def target_evaluation_func(self, current_labeling):
        #print(current_labeling)
        energy = self.calculate_energy(current_labeling)
        #print(energy)
        tempreture = 200000.0
        return mpmath.exp(-(energy/tempreture))

    def calculate_ground_truth(self, true_segment):
        true_labeling = []
        seg = 0
        ts_index = 0
        for i in range(0, self.all_nodes.node_num):
            if i == true_segment.seg_boundary[ts_index]:
                seg = 1 - seg
                true_labeling.append(seg)
                ts_index += 1
            else:
                true_labeling.append(seg)
        true_eval = self.target_evaluation_func(true_labeling)
        return true_eval

    def __labeling_to_segments(self, labeling):
        segmentation = []
        current_segment = []
        current_segment_label = labeling[0]
        for (node_index, label) in enumerate(labeling):
            if label == current_segment_label:
                current_segment.append(node_index)
            else:
                # New segment
                segmentation.append(current_segment)
                current_segment = [node_index]
                current_segment_label = label
        if len(current_segment) > 0:
            segmentation.append(current_segment)
        return segmentation

    def calculate_energy(self, current_labeling):
        """Energy Function: Category Posterior + Category Transition + Length Prior(Currently not included)"""
        assert(len(current_labeling) == self.all_nodes.node_num)
        segmentation = self.__labeling_to_segments(current_labeling)

        energy = 0.0
        previous_category = -1
        for segment in segmentation:
            # likelihood term
            [category, prob] = self.classification(segment)
            if prob == 0:
                prob = 1e-100
            energy += -mpmath.log(prob)

            # transition prob term
            if previous_category != -1:
                energy += -mpmath.log(self.transition_prob.get_value(category, previous_category) + 1e-100)
            previous_category = category

            # prior prob term
            energy += -mpmath.log(self.length_prior[len(segment) - 1])
        return energy

    def classification(self, current_seg):
        #np1_set = []
        #vp_set = []
        #np2_set = []
        #for i in current_seg:
        #    current_node = self.all_nodes.nodes[i]
        #    for w in current_node.NP1:
        #        np1_set.append(w)
        #    for w in current_node.VP:
        #        vp_set.append(w)
        #    for w in current_node.NP2:
        #        np2_set.append(w)
        #np1_cat_prob = self.calculate_prob_CatGivenWord(np1_set, self.np1_voc, self.np1_prob)
        #vp_cat_prob = self.calculate_prob_CatGivenWord(vp_set, self.vp_voc, self.vp_prob)
        #np2_cat_prob = self.calculate_prob_CatGivenWord(np2_set, self.np2_voc, self.np2_prob)
        [np1_cat_prob, vp_cat_prob, np2_cat_prob] = self.calculate_prob(current_seg)
        max_prob = -1.0
        label = -1
        for i in range(0, self.class_num):
            prob = mpmath.mpf(np1_cat_prob.get_value(0, i)) * mpmath.mpf(vp_cat_prob.get_value(0, i)) * mpmath.mpf(np2_cat_prob.get_value(0, i))
            if prob != 0:
                prob /= mpmath.mpf(self.class_prior.get_value(0, i) * self.class_prior.get_value(0, i))
            if prob > max_prob:
                max_prob = prob
                label = i
        return [label, max_prob]

    def calculate_prob(self, current_seg):
        np1_cat_prob = probability.Probability(1, self.class_num)
        vp_cat_prob = probability.Probability(1, self.class_num)
        np2_cat_prob = probability.Probability(1, self.class_num)
        for i in range(0, self.class_num):
            prob_np1 = mpmath.mpf(1.0)
            prob_vp = mpmath.mpf(1.0)
            prob_np2 = mpmath.mpf(1.0)
            for j in current_seg:
                prob_np1 *= mpmath.mpf(self.all_nodes.nodes[j].np1_probgivencat.get_value(0, i))
                prob_vp *= mpmath.mpf(self.all_nodes.nodes[j].vp_probgivencat.get_value(0, i))
                prob_np2 *= mpmath.mpf(self.all_nodes.nodes[j].np2_probgivencat.get_value(0, i))
            prior = mpmath.mpf(self.class_prior.get_value(0, i))
            prob_np1 *= prior
            prob_vp *= prior
            prob_np2 *= prior
            np1_cat_prob.set_value(0, i, prob_np1)
            vp_cat_prob.set_value(0, i, prob_vp)
            np2_cat_prob.set_value(0, i, prob_np2)
        return [np1_cat_prob, vp_cat_prob, np2_cat_prob]

    def calculate_prob_CatGivenWord(self, words, voc, voc_prob):
        word_id = []
        for w in words:
            if voc.contain(w):
                word_id.append(voc.get_word_index(w))
            else:
                word_id.append(-1)
        prob_all_cats = probability.Probability(1, self.class_num)
        for i in range(0, self.class_num):
            prob = 1
            for wid in word_id:
                if wid != -1:
                    if voc_prob.get_value(wid, i) == 0:
                        print('Error')
                    prob *= voc_prob.get_value(wid, i)
            prob *= self.class_prior.get_value(0, i)
            prob_all_cats.set_value(0, i, prob)
        return prob_all_cats
