import re

wiki_link_prefix = 'http://en.wikipedia.org/wiki/'


def read_csv_file(path):
    data = {}
    with open(path, 'r', encoding='utf8') as f:
        for line in f:
            comps = line.strip().split('\t')
            # [TODO] store query info
            doc_name = comps[0] + ' ' + comps[0]
            mention = comps[2]
            lctx = comps[3]
            rctx = comps[4]

            if comps[6] != 'EMPTYCAND':
                cands = [c.split(',') for c in comps[6:-2]]
                cands = [(','.join(c[2:]).replace('"', '%22').replace(' ', '_'), float(c[1])) for c in cands]
            else:
                cands = []

            gold = comps[-1].split(',')
            if gold[0] == '-1':
                gold = (','.join(gold[2:]).replace('"', '%22').replace(' ', '_'), 1e-5, -1)
            else:
                gold = (','.join(gold[3:]).replace('"', '%22').replace(' ', '_'), 1e-5, -1)

            if doc_name not in data:
                data[doc_name] = []
            data[doc_name].append({'mention': mention,
                                   'context': (lctx, rctx),
                                   'candidates': cands,
                                   'gold': gold})
    return data


def read_conll_file(data, path):
    conll = {}
    with open(path, 'r', encoding='utf8') as f:
        cur_sent = None
        cur_doc = None

        for line in f:
            line = line.strip()
            if line.startswith('-DOCSTART-'):
                docname = line.split()[1][1:]
                conll[docname] = {'sentences': [], 'mentions': []}
                cur_doc = conll[docname]
                cur_sent = []

            else:
                if line == '':
                    cur_doc['sentences'].append(cur_sent)
                    cur_sent = []

                else:
                    comps = line.split('\t')
                    tok = comps[0]
                    cur_sent.append(tok)

                    if len(comps) >=6 :
                        bi = comps[1]
                        wikilink = comps[4]
                        if bi == 'I':
                            cur_doc['mentions'][-1]['end'] += 1
                        else:
                            new_ment = {'sent_id': len(cur_doc['sentences']),
                                        'start': len(cur_sent) - 1,
                                        'end': len(cur_sent),
                                        'wikilink': wikilink}
                            cur_doc['mentions'].append(new_ment)

    # merge with data
    # also deal with overlapping mentions that were removed in conll files
    rmpunc = re.compile('[\W]+')
    empty_docs = []
    for doc_name, content in data.items():
        conll_doc = conll.get(doc_name.split()[0], None)

        if conll_doc is not None:
            m_id_to_del = []
            for i, m in enumerate(content):
                mention = m['mention']
                gold = m['gold']
                for cur_conll_m in conll_doc['mentions']:
                    cur_conll_mention = ' '.join(conll_doc['sentences'][cur_conll_m['sent_id']][cur_conll_m['start']:cur_conll_m['end']])
                    if rmpunc.sub('', cur_conll_mention.lower()) == rmpunc.sub('', mention.lower()):
                        m['conll_m'] = cur_conll_m
                        break
                if 'conll_m' not in m:
                    m_id_to_del.append(i)
            m_id_to_del.sort(reverse=True)
            for i in m_id_to_del:
                del data[doc_name][i]

        if len(data[doc_name]) == 0:
            empty_docs.append(doc_name)
        else:
            data[doc_name][0]['conll_doc'] = conll_doc
    for doc_name in empty_docs:
        print(doc_name, 'has no mentions. Removing it')
        del data[doc_name]
    return data


# def read_PPRforNED(data, path):
#     pat = re.compile('^[0-9]+')
#     rmpunc = re.compile('[\W]+')
#     for doc_name, content in data.items():
#         m = pat.match(doc_name)
#         if m is None:
#             raise Exception('doc_id not found in ' + doc_name)
#         doc_id = doc_name[m.start():m.end()]
#
#         # read PPRforNED file
#         new_content = []
#         with open(path + '/' + doc_id, 'r', encoding='utf8') as f:
#             m = None
#
#             for line in f:
#                 comps = line.strip().split('\t')
#                 if comps[0] == 'ENTITY':
#                     entity = comps[-1][4:].replace('"', '%22').replace(' ', '_')
#
#                     if entity == 'NIL':
#                         continue
#                     else:
#                         m = {}
#                         new_content.append(m)
#                         m['mention'] = comps[7][9:]
#
#                 elif comps[0] == 'CANDIDATE' and m is not None:
#                     cand = comps[5][len('url:' + wiki_link_prefix):].replace('"', '%22').replace(' ', '_')
#                     if 'candidates' not in m:
#                         m['candidates'] = []
#                     m['candidates'].append((cand, 1e-5))
#
#         i = 0
#         j = 0
#         while i < len(content) and j < len(new_content):
#             mi = content[i]
#             mj = new_content[j]
#             if rmpunc.sub('', mi['mention'].lower()) == rmpunc.sub('', mj['mention'].lower()):
#                 mi['PPRforNED_candidates'] = []
#                 cand_p = {c[0]:c[1] for c in m['candidates']}
#                 for cand, _ in mj['candidates']:
#                     mi['PPRforNED_candidates'].append((cand, cand_p.get(cand, 1e-3)))
#                 i += 1
#                 j += 1
#             else:
#                 j += 1


def load_person_names(path):
    data = []
    with open(path, 'r', encoding='utf8') as f:
        for line in f:
            data.append(line.strip().replace(' ', '_'))
    return set(data)


def find_coref(ment, mentlist, person_names):
    cur_m = ment['mention'].lower()
    coref = []
    for m in mentlist:
        if len(m['candidates']) == 0 or m['candidates'][0][0] not in person_names:
            continue

        mention = m['mention'].lower()
        start_pos = mention.find(cur_m)
        if start_pos == -1 or mention == cur_m:
            continue

        end_pos = start_pos + len(cur_m) - 1
        if (start_pos == 0 or mention[start_pos-1] == ' ') and \
                (end_pos == len(mention) - 1 or mention[end_pos + 1] == ' '):
            coref.append(m)

    return coref


def with_coref(dataset, person_names):
    for data_name, content in dataset.items():
        for cur_m in content:
            coref = find_coref(cur_m, content, person_names)
            if coref is not None and len(coref) > 0:
                cur_cands = {}
                for m in coref:
                    for c, p in m['candidates']:
                        cur_cands[c] = cur_cands.get(c, 0) + p
                for c in cur_cands.keys():
                    cur_cands[c] /= len(coref)
                cur_m['candidates'] = sorted(list(cur_cands.items()), key=lambda x: x[1])[::-1]


def eval(testset, system_pred):
    gold = []
    pred = []

    for doc_name, content in testset.items():
        gold += [c['gold'][0] for c in content]
        pred += [c['pred'][0] for c in system_pred[doc_name]]

    true_pos = 0
    for g, p in zip(gold, pred):
        if g == p and p != 'NIL':
            true_pos += 1

    precision = true_pos / len([p for p in pred if p != 'NIL'])
    recall = true_pos / len(gold)
    f1 = 2 * precision * recall / (precision + recall)
    return f1


class CoNLLDataset:
    """
    reading dataset from CoNLL dataset, extracted by https://github.com/dalab/deep-ed/
    """

    def __init__(self, path, person_path, conll_path):
        print('load csv')
        self.train = read_csv_file(path + '/aida_train.csv')
        self.testA = read_csv_file(path + '/aida_testA.csv')
        self.testB = read_csv_file(path + '/aida_testB.csv')
        self.ace2004 = read_csv_file(path + '/wned-ace2004.csv')
        self.aquaint = read_csv_file(path + '/wned-aquaint.csv')
        self.clueweb = read_csv_file(path + '/wned-clueweb.csv')
        self.msnbc = read_csv_file(path + '/wned-msnbc.csv')
        self.wikipedia = read_csv_file(path + '/wned-wikipedia.csv')
        self.wikipedia.pop('Jiří_Třanovský Jiří_Třanovský', None)
        self.tac2014 = read_csv_file(path + '/tac-kbp-2014.csv')

        print('process coref')
        person_names = load_person_names(person_path)
        with_coref(self.train, person_names)
        with_coref(self.testA, person_names)
        with_coref(self.testB, person_names)
        with_coref(self.ace2004, person_names)
        with_coref(self.aquaint, person_names)
        with_coref(self.clueweb, person_names)
        with_coref(self.msnbc, person_names)
        with_coref(self.wikipedia, person_names)
        with_coref(self.tac2014, person_names)

        print('load conll')
        read_conll_file(self.train, conll_path + '/AIDA/aida_train.txt')
        read_conll_file(self.testA, conll_path + '/AIDA/testa_testb_aggregate_original')
        read_conll_file(self.testB, conll_path + '/AIDA/testa_testb_aggregate_original')
        read_conll_file(self.ace2004, conll_path + '/wned-datasets/ace2004/ace2004.conll')
        read_conll_file(self.aquaint, conll_path + '/wned-datasets/aquaint/aquaint.conll')
        read_conll_file(self.msnbc, conll_path + '/wned-datasets/msnbc/msnbc.conll')
        read_conll_file(self.clueweb, conll_path + '/wned-datasets/clueweb/clueweb.conll')
        read_conll_file(self.wikipedia, conll_path + '/wned-datasets/wikipedia/wikipedia.conll')
        read_conll_file(self.tac2014, conll_path + '/tac-kbp/2014/tac-kbp-2014.conll')


if __name__ == "__main__":
    path = 'data/generated/test_train_data/'
    conll_path = 'data/basic_data/test_datasets/'
    person_path = 'data/basic_data/p_e_m_data/persons.txt'

    conll = CoNLLDataset(path, person_path, conll_path)
    # from pprint import pprint
    # pprint(conll.tac2014, width=200)

    dev_datasets = [('aida-A', conll.testA),
                    ('aida-B', conll.testB),
                    ('msnbc', conll.msnbc),
                    ('aquaint', conll.aquaint),
                    ('ace2004', conll.ace2004),
                    ('clueweb', conll.clueweb),
                    ('wikipedia', conll.wikipedia),
                    ('tackbp2014', conll.tac2014)
                    ]
    for di, (dname, _) in enumerate(dev_datasets):
        dev_set = dev_datasets[di][1]
        predictions = { doc_name: [ { 'pred': c['candidates'][0] if len(c['candidates']) > 0 else 'NIL' } for c in content ]
            for doc_name, content in dev_set.items() }
        print(dname, '#doc:', len(dev_set))
        print(dname, '#mentions/doc:',
                sum(len(content) for content in dev_set.values()) / len(dev_set))
        print(dname, 'micro F1: ' + str(eval(dev_datasets[di][1], predictions)))
