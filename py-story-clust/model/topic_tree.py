import logging
import math

# constants
NUM_WODE_TYPE = 3
WORD_TYPE_NP1 = 0
WORD_TYPE_VP = 1
WORD_TYPE_NP2 = 2


class TopicTree(object):
    def __init__(self, corpus_stat):
        super(TopicTree, self).__init__()
        self.nodes = range(0, corpus_stat.size())
        self.corpus_stat = corpus_stat
        self.branch_stats = corpus_stat.documents_stats
        self.branch_terminals = [[x] for x in self.nodes]

    def combine_branch(self, i, j):
        # combine node
        self.nodes[i] = [self.nodes[i]]
        self.nodes[i].append(self.nodes[j])
        self.nodes.pop(j)

        # transfer the terminals' ownership
        self.branch_terminals[i].extend(self.branch_terminals[j])
        self.branch_terminals.pop(j)

        # combine branch distribution
        self.branch_stats[i].combine(self.branch_stats[j])
        self.branch_stats.pop(j)

    def find_branch_id(self, target_terminal):
        for (branch_id, terminals) in enumerate(self.branch_terminals):
            if target_terminal in terminals:
                return branch_id
        raise ValueError('Cannot find target terminal node: {0}'.format(target_terminal))

    def synthesis_title(self, branch_id):
        """Synthesis ID"""

    def print_hiearchy(self, root=None, labels=None, level_indents=0):
        if root is None:
            root = self.nodes
        print('{0}+'.format(level_indents*'|  '))
        for node in root:
            if isinstance(node, type([])):
                # Have next level
                self.print_hiearchy(node, labels=labels, level_indents=level_indents+1)
            else:
                if labels is not None:
                    label_to_print = labels[node]
                else:
                    label_to_print = node
                print('{0}{1}{2}'.format((level_indents)*'|  ', '|- ', label_to_print))

    def prior(self):
        """Returns the prior of the tree based on complexity.
        Simple trees are favored."""
        return math.exp(-len(self.branch_stats) * 10)  # * 1e30

    def likelihood(self, corpus, subset=None):
        """Calculate the likelihood of the corpus of current topic tree."""
        likelihood = 0
        for (doc_id, document) in enumerate(corpus.documents):
            # Only computer the likelihood of affected portion of data
            if subset is None or doc_id in subset:
                # The likelihood is calculated on the main branch.
                target_branch_id = self.find_branch_id(doc_id)

                prob_doc = 0
                for type_id in range(0, NUM_WODE_TYPE):
                    if (len(document.word_lists[type_id]) == 0):
                        continue
                        #raise ValueError('Empty list in document {0}, list {1}'.format(
                        #    document.name, type_id))
                    prob_type = 0
                    for word in document.word_lists[type_id]:
                        # calculate log likelihood
                        prob_doc += math.log(self.get_probability(target_branch_id, word, type_id))
                    prob_type /= len(document.word_lists[type_id])
                    prob_doc += prob_type

                likelihood += prob_doc
        #assert(likelihood != 0)
        return likelihood

    def get_probability(self, branch_id, word, type_id):
        try:
            word_id = self.corpus_stat.vocabularies[type_id].get_word_index(word)
            distribution = self.branch_stats[branch_id].distributions[type_id]
            assert(distribution[word_id] > 0)
            return distribution[word_id]
        except ValueError:
            logging.warning('Cannot find word: {0}   (type {1})'.format(word, type_id))
            return 1
