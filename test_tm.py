import argparse 
import logging
import pickle
import random

import numpy as np

from space import Space
from dinu14.utils import read_dict, apply_tm, score, get_invocab_trans
from utils import get_logger, default_output_fn


class MxTester():
    def __init__(self, args, tr_mx=None, exclude_from_test=None):
        self.additional = args.additional
        self.args = args
        self.tr_mx = tr_mx
        self.exclude_from_test = exclude_from_test

    def load_tr_mx(self):
        if self.args.mx_path:
            if self.tr_mx or self.exclude_from_test:
                raise Exception(
                    "Translation mx or training words specified amibiguously.")
            else:
                self.args.mx_path = default_output_fn(
                    self.args.mx_path, self.args.seed_fn, self.args.source_fn,
                    self.args.target_fn)
                logging.info("Loading from {}".format(self.args.mx_path))
                self.exclude_from_test = pickle.load(open(
                    '{}.train_wds'.format(self.args.mx_path)))
                self.tr_mx = np.load('{}.npy'.format(self.args.mx_path))
        elif self.tr_mx is None or not self.exclude_from_test:
            raise Exception('Translation matrix or training words unspecified')

    def test_wrapper(self):
        self.load_tr_mx()

        logging.info('The denominator of precision {} OOV words'.format(
                          'includes' if self.args.coverage 
                          else "doesn't include"))
        test_wpairs = read_dict(self.args.seed_fn, reverse=self.args.reverse,
                                needed=1000 if self.args.coverage else -1,
                                exclude=self.exclude_from_test)

        source_sp = self.build_src_wrapper(self.args.source_fn, test_wpairs)

        target_sp = Space.build(self.args.target_fn)
        target_sp.normalize()

        test_wpairs, _ = get_invocab_trans(source_sp, target_sp,
                                              test_wpairs, needed=1000)

        """
        #turn test data into a dictionary (a word can have mutiple translation)
        gold = collections.defaultdict(set, test_wpairs)
        for sr, tg in test_wpairs:
            gold[sr].add(tg)
            """

        logging.info(
            "Mapping all the elements loaded in the source space")
        mapped_source_sp = apply_tm(source_sp, self.tr_mx)
        if hasattr(self.args, 'mapped_vecs') and self.args.mapped_vecs:
            logging.info("Printing mapped vectors: %s" % self.args.mapped_vecs)
            np.savetxt("%s.vecs.txt" % self.args.mapped_vecs, mapped_source_sp.mat)
            np.savetxt("%s.wds.txt" %
                       self.args.mapped_vecs, mapped_source_sp.id2word, fmt="%s")

        return score(mapped_source_sp, target_sp, test_wpairs, self.additional)

    def build_src_wrapper(self, source_file, test_wpairs):
        """
        In the _source_ space, we only need to load vectors for the words in
        test.  Semantic spaces may contain additional words.
        All words in the _target_ space are used as the search space
        """
        source_words = set(test_wpairs.iterkeys())
        if self.additional:
            #read all the words in the space
            lexicon = set(np.loadtxt(source_file, skiprows=1, dtype=str,
                                        comments=None, usecols=(0,)).flatten())
            #the max number of additional+test elements is bounded by the size
            #of the lexicon
            self.additional = min(self.additional, len(lexicon) - len(source_words))
            random.seed(100)
            logging.info("Sampling {} additional elements".format(self.additional))
            # additional lexicon:
            lexicon = random.sample(list(lexicon.difference(source_words)),
                                    self.additional)

            #load the source space
            source_sp = Space.build(source_file,
                                    lexicon=source_words.union(set(lexicon)),
                                    max_rows=1000)
        else:
            source_sp = Space.build(source_file, lexicon=source_words,
                                    max_rows=1000) 
        source_sp.normalize()
        return source_sp


def parse_args():
    parser = argparse.ArgumentParser(
    description="Given a translation matrix, test data (words and their\
        translations) and source and target language vectors, it returns\
        translations of source test words and computes Top N accuracy.",
        epilog='\n\
        Example:\n\
        1) Retrieve translations with standard nearest neighbour retrieval\n\
        \n\
        python test_tm.py tm.npy test_wpairs.txt ENspace.txt ITspace.txt\n\
        \n\
        2) "Corrected" retrieval (GC). Use additional 2000 source space\n\
        elements to correct for hubs (words that appear as the nearest\n\
        neighbours of many points))\n\
        \n\
        python -c 2000 test_tm.py tm.npy test_wpairs.txt ENspace.txt ITspace.txt')
    parser.add_argument('--mx_path',
                        help='directory or file name without extension',
                        default='/mnt/store/makrai/project/multiwsi/trans-mx/')
    parser.add_argument(
        'seed_fn',
        help="train dictionary, list of word pairs (space separated words,\
        one word pair per line")
    parser.add_argument(
        'source_fn',
        help="vectors in source language. Space-separated, with string\
        identifier as first column (dim+1 columns, where dim is the\
        dimensionality of the space")
    parser.add_argument(
        'target_fn',
        help="vectors in target language")
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument(
        '--additional', type=int,
        help='Number of elements (additional to test data) to be used with\
        Global Correction (GC) strategy.')
    parser.add_argument('-o', '--log-file', dest='log_fn')
    parser.add_argument(
        '--mapped_vecs',
        help='File prefix. It prints the vectors obtained after the\
        translation matrix is applied (.vecs.txt and .wds.txt).')
    parser.add_argument(
        '--just-recall', action='store_false', dest='coverage')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if hasattr(args, 'log_fn'):
        get_logger(args.log_fn)
    MxTester(args).test_wrapper()
