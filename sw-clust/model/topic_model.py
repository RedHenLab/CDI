import sys
import datetime
import logging
sys.path.append('..')

import numpy as np
import mpmath
from scipy.stats import norm
import matplotlib.pyplot as plt

from model import *
from preprocessing import vocabulary
from algorithm import sw


class _Plotter(object):
    def __init__(self, sw_config):
        self.iterations = []
        self.energies = []
        self.temperatures = []
        self._sw_config = sw_config

        plt.ion()
        self.fig = plt.figure(figsize=(16, 10))
        #self.energy_plot = self.fig.add_subplot(211)
        #self.segment_plot = self.fig.add_subplot(212)
        self.energy_plot = self.fig.add_subplot(plt.subplot2grid((1, 3), (0, 0), colspan=2))
        self.temperature_plot = self.fig.add_subplot(plt.subplot2grid((1, 3), (0, 2)))

    def plot_callback(self, clustering, context):
        for cluster in clustering:
            for doc_id in cluster:
                print(self._sw_config.documents[doc_id].name)
            print('')

        self.iterations.append(context.iteration_counter)
        self.energies.append(self._sw_config.energy(clustering))
        self.temperatures.append(self._sw_config.cooling_schedule(context.iteration_counter))

        # energy plot
        self.energy_plot.clear()
        self.energy_plot.set_title('Energy')
        self.energy_plot.plot(self.iterations, self.energies)

        # temperature plot
        self.temperature_plot.clear()
        self.temperature_plot.set_title('Temperature')
        self.temperature_plot.plot(self.iterations, self.temperatures)

        self.fig.canvas.draw()

    def save(self):
        self.fig.savefig('multi_level_plot.png', transparent=False, bbox_inches=None, pad_inches=0.1)


class SWConfig(object):
    """One shall inherit this class to give more specific configurations."""
    def __init__(self, graph_size, edges, vertex_distributions, documents, level):
        self.graph_size = graph_size
        self.edges = edges
        self.monitor_statistics = self.energy
        self.vertex_distributions = vertex_distributions
        self.level = level
        self.documents = documents

        # cache
        self._likelihood_cache = dict()
        self._kl_cache = dict()

    def _kl_key(self, s, t):
        return '{0}, {1}'.format(s, t)

    def edge_prob_func(self, s, t, context):
        """Calculate edge probability based on KL divergence."""
        #logging.debug('Calaulate Edge Prob {0}, {1}'.format(s, t))
        kl_value_all = 0.0

        # Cache KL divergence between two vertexes.
        kl_key = self._kl_key(s, t)
        if kl_key in self._kl_cache:
            kl_value_all = self._kl_cache[kl_key]
        else:
            for word_type in WORD_TYPES:
                p = self.vertex_distributions[s][word_type]
                q = self.vertex_distributions[t][word_type]
                kl_pq = p.kl_divergence(q)
                kl_qp = q.kl_divergence(p)
                kl_value_all += kl_pq
                kl_value_all += kl_qp
            kl_value_all /= 3
            self._kl_cache[kl_key] = kl_value_all

        #temperature = self.cooling_schedule(context.iteration_counter)
        edge_prob = mpmath.exp(-kl_value_all/(2*1000))
        return edge_prob

    def target_eval_func(self, clustering, context=None):
        temperature = self.cooling_schedule(context.iteration_counter)
        target = mpmath.exp(- self.energy(clustering) / temperature)
        return target

    def energy(self, clustering):
        energy = 0.0
        # TODO: target function may depend on level.
        # Candidate terms: likelihood, time prior, and etc.
        #     energy += -mpmath.log(P)

        new_vertex_distribution = _combine_vertex_distributions_given_clustering(
            self.vertex_distributions, clustering)
        energy += -self._log_likelihood(clustering, new_vertex_distribution)
        if self.level == 1:
            for cluster in clustering:
                energy += -mpmath.log(self._time_prior(cluster))
        return energy

    def _log_likelihood(self, clustering, new_vertex_distribution, weights=[1]*NUM_WORD_TYPE):
        likelihood = 0.0
        for i, cluster in enumerate(clustering):
            # Cache the likelihood of cluster to reduce duplicate computation.
            current_cluster_likelihood = 0.0
            if new_vertex_distribution[i] in self._likelihood_cache:
                current_cluster_likelihood = self._likelihood_cache[new_vertex_distribution[i]]
            else:
                for doc in new_vertex_distribution[i].document_ids:
                    for word_type in WORD_TYPES:
                        for word_id in self.documents[doc].word_ids[word_type]:
                            current_cluster_likelihood = weights[word_type] * mpmath.log(new_vertex_distribution[i][word_type][word_id] + 1e-100)
                self._likelihood_cache[new_vertex_distribution[i]] = current_cluster_likelihood
            likelihood += current_cluster_likelihood
        likelihood /= sum(weights)
        return likelihood

    def _time_prior(self, cluster):
        time_series = []
        for doc_id in cluster:
            time_series.append(self.documents[doc_id].timestamp)
        time_series.sort()
        dif = 0.0
        for i in range(0, len(time_series)-1):
            date_dif = time_series[i+1] - time_series[i]
            dif += date_dif.days
        dif /= (len(time_series))
        return mpmath.mpf(norm(1, 5).pdf(dif))

    def cooling_schedule(self, iteration_counter):
        # TODO: Cooling schedule may depend on level.
        starting_temperature = 10000
        period = 2
        step_size = 10

        temperature = starting_temperature - int(iteration_counter/period)*step_size
        if temperature <= 10:
            temperature = 10
        return temperature


def _combine_vertex_distributions_given_clustering(current_vertex_distributions, clustering):
    # create new vertex distribution
    new_vertex_distributions = []
    for cluster in clustering:
        vertex_distribution = _VertexDistribution()
        for v in cluster:
            vertex_distribution += current_vertex_distributions[v]
        new_vertex_distributions.append(vertex_distribution)
    return new_vertex_distributions


class TopicModel(object):
    def __init__(self):
        self.corpus = None
        self.topic_tree = _Tree()
        self.date_range = None
        #self.monitor = ModelMonitor()
        pass

    def feed(self, new_corpus):
        # Do Segmentation (if not segmented)
        #if not new_corpus.segmented:
            # TODO: Do segmentation first
        #    pass

        if self.corpus is None:
            self.corpus = new_corpus
        else:
            # Inference and attach to trees
            for document in new_corpus.documents:
                self._inference(document)
                self.corpus.add_document(document)

        # Reform the tree if necessary.
        if (self._need_reform()):
            self._reform_by_multilevel_sw()
        pass

    def _inference(self, new_document):
        """Inference and attach the new document to the current topic tree."""
        # TODO: This shall base on the likelihood and depth prior.
        pass

    def _reform_by_multilevel_sw(self):
        """Reform the whole tree by doing multi-level SW-Cuts."""

        need_next_level = True
        level_counter = 0

        # Initially, each document is a vertex.
        current_vertex_distributions = []

        # Initial clustering treat all vertex in the same cluster.
        current_clustering = [set(range(0, len(self.corpus)))]
        print(current_clustering)

        while need_next_level:
            level_counter += 1
            config = self._generate_next_sw_config(
                current_vertex_distributions, current_clustering, level_counter)
            plotter = _Plotter(config)

            # Clustering by SW.
            current_clustering = sw.sample(
                config.graph_size,
                config.edges,
                config.edge_prob_func,
                config.target_eval_func,
                intermediate_callback=plotter.plot_callback,
                initial_clustering=None,
                monitor_statistics=config.monitor_statistics)
            current_vertex_distributions = config.vertex_distributions

            # Save current clustering as a new level to the tree.
            # self._add_level_to_tree(current_clustering)

            # Determine if need more level.
            # TODO: determine if need next level.
            need_next_level = True
        pass

    def _generate_initial_vertex_distributions(self):
        initial_vertex_distributions = []
        for (doc_id, document) in enumerate(self.corpus):
            vertex_distribution = _VertexDistribution()
            vertex_distribution.document_ids = [doc_id]
            for word_type in WORD_TYPES:
                vertex_distribution[word_type] = self.corpus.get_dococument_distribution(doc_id, word_type, include_ocr=True)
            initial_vertex_distributions.append(vertex_distribution)
        return initial_vertex_distributions

    def _generate_next_sw_config(self, current_vertex_distributions, current_clustering, level_counter):
        """Generate sw configuration for next run base on current clustering result."""
        # TODO: give different configurations based on level.

        if level_counter == 1:
            graph_size = len(self.corpus)
            next_vertex_distributions = self._generate_initial_vertex_distributions()
        else:
            graph_size = len(current_clustering)
            # create new vertex distribution
            next_vertex_distributions = _combine_vertex_distributions_given_clustering(
                current_vertex_distributions, current_clustering)

        # Generate the edges. Delete some edges in the complete graph using some criteria.
        edges = []
        # TODO: Decide the threshold based on the current level
        distance_threshold = 0.8*level_counter
        for i in range(0, graph_size-1):
            for j in range(i+1, graph_size):
                distance = 0.0
                for word_type in WORD_TYPES:
                    dist_i = next_vertex_distributions[i][word_type]
                    dist_j = next_vertex_distributions[j][word_type]
                    distance += dist_i.tv_norm(dist_j)
                distance /= NUM_WORD_TYPE
                logging.debug('d({0}, {1}) = {2}'.format(i, j, distance))
                if distance <= distance_threshold:
                    edges.append((i, j))

        logging.debug(edges)
        logging.debug('# of vertex: {0}'.format(graph_size))
        logging.debug('# of edges: {0} [complete: {1}]'.format(len(edges), (graph_size*(graph_size-1)/2)))

        config = SWConfig(graph_size, edges, vertex_distributions=next_vertex_distributions, documents=self.corpus.documents, level=level_counter)
        return config

    def _need_reform(self):
        """Returns if the current topic_tree needs reforming."""
        # TODO: Add other criterion for judging whether reforming the tree
        #       is needed, like Dunn Index, Davies-Bouldin Index, etc.
        return True

    def _add_level_to_tree(self, current_clustering):
        """Add a level to tree."""
        self.topic_tree.add_level_on_top(current_clustering)
        pass


#class ModelMonitor():
#    def __init__(self):
#        self.last_reform_date = datetime.datetime.now() - datetime.timedelta(year=1)
#        self.reform_counter = 0

#    def update_reform_time(self):
#        self.last_reform_date = datetime.datetime.now()
#        self.reform_counter += 1


#
# Definitions for Topic Tree.
#
class _TreeNode(object):
    def __init__(self):
        self._children = []
        self._vp_distribution = None
        self._np1_distribution = None
        self._np2_distribution = None

    def add_child(self, node):
        self._children.append(node)
        # TODO: merge distribution after add a child
        # What if add a node to a terminal node (document).

    def get_child(self, index):
        return self._children[index]

    def is_terminal(self):
        return (len(self._children) == 0)


class _Tree(object):
    """A Tree structure."""
    def __init__(self):
        self._root = _TreeNode()

    def add_to_root(self, node):
        """Add a node to the root."""
        self._root.add_child(node)

    def add_level_on_top(self, clustering):
        """Add a new level on the top of the tree."""
        # e.g. clustering = [{1,2,3}, {4,5}, {5,6,7}]
        new_root = _TreeNode()
        for cluster in clustering:
            new_parent_node = _TreeNode()
            for vertex_index in cluster:
                new_parent_node.add_child(self._root.get_child(vertex_index))
        self._root = new_root


#
# Definitions for corpus and document.
#
class Corpus(object):
    """A Corpus object includes all documents' feature and corpus vocabulary."""
    def __init__(self):
        self.documents = []
        np1_vocab = vocabulary.Vocabulary()
        vp_vocab = vocabulary.Vocabulary()
        np2_vocab = vocabulary.Vocabulary()
        self.vocabularies = [np1_vocab, vp_vocab, np2_vocab]

    def __len__(self):
        return len(self.documents)

    def __iter__(self):
        return iter(self.documents)

    def __getitem__(self, document_id):
        return self.documents[document_id]

    def add_document(self, original_doc):
        """Convert document to feature and save into document list."""
        document_feature = self._convert_doc_to_feature(original_doc)
        self.documents.append(document_feature)

    def get_dococument_distribution(self, doc_id, word_type, include_ocr=False):
        histogram = np.zeros(self.vocabulary_size(word_type))
        for word_id in self.documents[doc_id].word_ids[word_type]:
            histogram[word_id] += 1

        # Include OCR in the distribution.
        if include_ocr:
            for ocr_word in self.documents[doc_id].ocr_words:
                if ocr_word in self.vocabularies[word_type]:
                    word_id = self.vocabularies[word_type].get_word_index(ocr_word)
                    self.documents[doc_id].word_ids[word_type].append(word_id)
                    histogram[word_id] += 1
        return _Distribution(histogram)

    def _convert_doc_to_feature(self, original_doc):
        document_feature = _DocumentFeature(original_doc.filename, original_doc.timestamp)
        document_feature.ocr_words = original_doc.ocr_words

        for word_type in WORD_TYPES:
            document_feature.word_ids[word_type] = self._convert_words_to_ids(word_type, original_doc.word_lists[word_type])
        return document_feature

    def _convert_words_to_ids(self, word_type, word_list):
        assert(word_type < NUM_WORD_TYPE)
        ids = []
        for word in word_list:
            # If word is in current vocabulary, we directly look up the word_id.
            # Otherwise, we add this word to the vocabulary and then look up.
            if word not in self.vocabularies[word_type]:
                self.vocabularies[word_type].add(word)
            word_id = self.vocabularies[word_type].get_word_index(word)
            ids.append(word_id)
        return ids

    def get_document_name(self, doc_id):
        return self.documents[doc_id].name

    def vocabulary_size(self, word_type):
        assert(word_type < NUM_WORD_TYPE)
        return self.vocabularies[word_type].size()


class _DocumentFeature(object):
    def __init__(
            self,
            name,
            timestamp,
            np1_word_ids=None,
            vp_word_ids=None,
            np2_word_ids=None,
            ocr_words=None):
        self.name = name
        self.timestamp = timestamp
        self.word_ids = [np1_word_ids, vp_word_ids, np2_word_ids]
        self.ocr_words = ocr_words


class _VertexDistribution:
    # Three _Distribution objects
    def __init__(self):
        self.distributions = [None] * NUM_WORD_TYPE
        self.document_ids = []

    def __getitem__(self, word_type):
        assert(word_type < NUM_WORD_TYPE)
        return self.distributions[word_type]

    def __setitem__(self, word_type, distribution):
        assert(word_type < NUM_WORD_TYPE)
        self.distributions[word_type] = distribution

    def __add__(self, other):
        result = _VertexDistribution()
        self.document_ids.extend(other.document_ids)
        self.document_ids.sort()
        for word_type in WORD_TYPES:
            if self.distributions[word_type] is None:
                result.distributions[word_type] = other.distributions[word_type]
            else:
                result.distributions[word_type] = self.distributions[word_type] + other.distributions[word_type]
        return result

    def __radd__(self, other):
        return self.__add__(other)

    def __iadd__(self, other):
        return self.__add__(other)

    def __hash__(self):
        """Make it hashable. The key is the the string format of sorted document id list.
        key =  str(document_ids)
        e.g. '[10, 11, 12]' is the key for [10, 11, 12]
        """
        return hash(str(self.document_ids))

    def __eq__(self, other):
        return hash(self) == hash(other)


class _Distribution(object):
    """A 1D histogram (normalized to 1)."""
    def __init__(self, histogram=None):
        if histogram is not None:
            self.set_histogram(histogram)
        else:
            self._hist = None
            self._denominator = 1
            self._length = 0

    def set_histogram(self, histogram):
        self._hist = histogram
        self._denominator = sum(histogram)
        self._length = len(histogram)
        if self._denominator != 1 and self._denominator != 0:
            self._hist /= self._denominator

    def __getitem__(self, word_id):
        if self._hist is not None:
            return self._hist[word_id]
        else:
            raise ValueError('The distribution is empty.')

    def __add__(self, other):
        # Recover histogram and add.
        if self._hist is not None:
            new_hist = self._hist * self._denominator + other._hist * other._denominator
            return _Distribution(new_hist)
        else:
            return other

    def __radd__(self, other):
        # The 'add' operation among distribution if symmetric.
        return self.__add__(other)

    def __iadd__(self, other):
        return self.__add__(other)

    def kl_divergence(self, other):
        p = self._hist
        q = other._hist
        assert(self._length == other._length)
        kl_array = [p[i]*(mpmath.log(p[i] + 1e-100) - mpmath.log(q[i] + 1e-100)) for i in range(0, self._length)]
        kl_value = sum(kl_array)
        return kl_value

    def tv_norm(self, other):
        assert(self._length == other._length)
        diff = np.absolute(self._hist - other._hist)
        return mpmath.mpf(np.sum(diff))/2.0

    def combine(self, other):
        self = self.__add__(other)

    def synthesize(self, num_words):
        """Synthesize a set of words from the distribution."""
        indexes = np.argsort(self._hist)
        top_words_id = indexes[::-1][0:min(num_words, len(self._hist))]
        return top_words_id.tolist()
