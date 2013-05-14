# Learn co-occurrence matrix from data
import codecs
import logging
import math
import numpy as np

from vocabulary import vocabulary


def learn_matrix(story_files):
    """Learn a word co-occurrence matrix from corpus."""

    logging.debug("Calculating matrix from {0} files".format(len(story_files)))
    # build vocabulary
    vocab = build_vocabulary(story_files)
    vocab.save('vocabulary.voc')

    # build matrix and fill in
    matrix = build_cooccur_matrix(vocab, story_files)
    save_matrix('co_mat.npy', matrix)
    return matrix


def build_vocabulary(story_files):
    """Build a vocabulary from a set of given tpt files."""
    voc = vocabulary.Vocabulary()

    for story_file in story_files:
        words = read_story(story_file)
        for w in words:
            voc.add(w)

    logging.debug('Vocabulary obtained: {0} words.'.format(voc.size()))
    logging.debug('Print 15 words:')
    for i in range(0, 15):
        logging.debug('{0}: {1}'.format(i, voc.get_word(i)))
    return voc


def build_cooccur_matrix(vocab, story_files):
    """Build co-occurrence matrix."""
    # TODO: fill in co-occurrence matrix
    num_words = vocab.size()
    contextual_dist = np.zeros((num_words, num_words))

    for story_file in story_files:
        words = read_story(story_file)
        wordset = set(words)

        # frequencies = [ (u_id, v_id, p_u(v))]
        frequencies = [(vocab.get_word_index(u), vocab.get_word_index(v),
            words.count(u)*words.count(v)) for u in wordset for v in wordset]

        for element in frequencies:
            #logging.debug("{0}, {1} = {2}".format(
            #    element[0], element[1], element[2]))
            if element[0] == element[1]:
                contextual_dist[element[0], element[1]] += math.sqrt(element[2])
            else:
                contextual_dist[element[0], element[1]] += element[2]

    # normalize so that each row will sum to one.
    row_sums = contextual_dist.sum(axis=1)
    contextual_dist = contextual_dist / row_sums.reshape(-1, 1)

    logging.debug('Print 15*15 contextual distribution:')
    logging.debug(contextual_dist[0:15, 0:15])
    logging.debug(contextual_dist[np.ix_([1, 3, 5], [1, 3, 5])])

    co_matrix = np.zeros((num_words, num_words))

    # only calculate the upper triangle matrix
    for u in range(0, num_words):
        for v in range(u, num_words):
            sqrt_sum = ((contextual_dist[u] * contextual_dist[v])**0.5).sum()
            #logging.debug('sqrt = {0}'.format(sqrt_sum))
            power = 0
            if sqrt_sum >= 1:
                if math.fabs(sqrt_sum - 1.0) > 0.00001:
                    logging.warning('sqrt_sum >= 1 is {0}'.format(sqrt_sum))
                power = 0
            else:
                power = math.acos(sqrt_sum) ** 2
            co_matrix[u, v] = math.exp(-1 * power)
    # recover the whole matrix
    co_matrix = co_matrix + np.tril(co_matrix.T, -1)

    logging.debug('Print 15*15 similarity matrix:')
    logging.debug(co_matrix[0:15, 0:15])

    return co_matrix


def save_matrix(filename, matrix):
    np.save(filename, matrix)
    return


def read_story(filename):
    with codecs.open(filename, 'r', encoding='ISO-8859-1') as f:
        content = f.read()
    words = content.split()
    return words
