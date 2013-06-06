# This file defines classes to model corpus:


class Corpus(object):
    """A Corpus object includes all documents' content and corpus statistics."""
    def __init__(self, corpus_stat):
        self.statistics = corpus_stat
        self.documents = []

    def add_document(self, doc, doc_stat):
        self.documents.append(doc)
        self.statistics.add_doc_stat(doc_stat)

    def get_document_name(self, doc_id):
        return self.documents[doc_id].name

    def size(self):
        return len(self.documents)


class CorpusStatistics(object):
    """Corpus statistics contains vocabulary used and document statistics."""
    def __init__(self, np1_vocab, vp_vocab, np2_vocab):
        self.documents_stats = []
        self.vocabularies = (np1_vocab, vp_vocab, np2_vocab)
        pass

    def add_doc_stat(self, document_stat):
        self.documents_stats.append(document_stat)

    def size(self):
        return len(self.documents_stats)


class Document(object):
    """Content of a document, including filename and all types of word lists."""
    def __init__(self, name, np1_words, vp_words, np2_words, ocr_words):
        self.name = name
        self.word_lists = (np1_words, vp_words, np2_words, ocr_words)


class DocumentStatistics(object):
    """Statistics of a document. This contains a distribution for each type of word."""
    def __init__(self, distributions, ocr_words=None):
        self.distributions = distributions
        if ocr_words is None:
            self.ocr_words = []
        else:
            self.ocr_words = ocr_words

    def combine(self, other_document):
        for (i, dist) in enumerate(self.distributions):
            self.distributions[i].combine(other_document.distributions[i])
        self.ocr_words.extend(other_document.ocr_words)


class Distribution(object):
    """Histogram (normalized to 1)."""
    def __init__(self, hist, denominator):
        self.hist = hist
        self.denominator = denominator

    def combine(self, other):
        # Recover the histogram before normalization and add up two histograms
        self.hist = self.hist * self.denominator + other.hist * other.denominator

        # Re-normalize to 1
        denominator = self.hist.sum()
        if denominator != 0:
            self.hist /= denominator
        self.denominator = denominator

    def __getitem__(self, word_id):
        return self.hist[0, word_id]
