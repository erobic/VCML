from dataset.tools import protocol
import numpy as np
from tqdm import tqdm
from utils.common import random_one
import sys
args = sys.args
info = sys.info

class ToyDataset:

    def __init__(self):
        pass

    @classmethod
    def build_visual_dataset(cls):
        vocabulary = protocol.Protocol(False, '', gather=True, use_special_tokens=False)
        for i in range(args.toy_attributes):
            cat = min((i * args.toy_categories) // (args.toy_attributes),
                      args.toy_categories)
            attr_name = 'attr_%.2d' % i
            vocabulary['cat_{}'.format(cat), attr_name]

        sceneGraphs = {}
        print('building teddy sceneGraphs')
        for i in tqdm(range(args.max_sizeDataset)):
            split =\
                'train' if i < 0.8 * args.max_sizeDataset or args.no_validation else\
                'val' if i < 1 * args.max_sizeDataset else\
                'test'
            scene = {'objects': {}, 'split': split, 'image_id': format(i)}
            for j in range(args.toy_objects):
                categories = np.random.choice(list(vocabulary.records),
                                              args.toy_attributesPobject,
                                              replace=False)
                obj = {cat: random_one(vocabulary[cat])
                       for cat in categories}
                scene['objects'].update({str(len(scene['objects'])): obj})
            sceneGraphs[str(i)] = scene
        return sceneGraphs


    @classmethod
    def build_question_dataset(cls, visual_dataset, config):
        questions = {}
        all_concepts = {k: [k] for k in info.vocabulary['total']}
        if config == 'partial':
            for attr in args.bias_config:
                if attr in all_concepts:
                    all_concepts.pop(attr)
        elif config == 'replaced':
            for attr in args.bias_config:
                if attr in all_concepts:
                    all_concepts[attr] = [attr+'_syn']
        elif 'synonym' in args.subtask:
            for attr in all_concepts:
                all_concepts[attr] = [attr, attr+'_syn']
                all_concepts[attr+'_syn'] = [attr, attr+'_syn']

        args.task_concepts['all_concepts'] = set(list(all_concepts.keys())+
                                                 [at for attrs in all_concepts.values()
                                                  for at in attrs])

        if 'synonym' in args.subtask or 'query_isinstance' in args.subtask:
                #or args.subtask == 'filter_isinstance':
            task_concepts = {}
            if args.val_concepts:
                assert set(args.val_concepts).issubset(set(all_concepts)), 'outside concept set'
                task_concepts['val'] = args.val_concepts
            else:
                task_concepts['val'] = np.random.choice(list(all_concepts),
                                                        int(len(all_concepts)*args.generalization_ratio),
                                                        replace=False)
            task_concepts['train'] = np.setdiff1d(list(all_concepts), task_concepts['val'])
            task_concepts['total'] = all_concepts
            args.task_concepts[config] = task_concepts
        elif 'filter_isinstance' in args.subtask:
            task_concepts = {}
            if args.val_concepts:
                assert set(args.val_concepts).issubset(set(all_concepts)), 'outside concept set'
                task_concepts['val'] = args.val_concepts
            else:
                task_concepts['val'] =  np.random.choice(info.vocabulary['color']
                                                        if 'color' in info.vocabulary.records
                                                        else list(all_concepts),
                                                        int(len(all_concepts)*args.generalization_ratio),
                                                        replace=False)
            task_concepts['train'] = np.setdiff1d(list(all_concepts), task_concepts['val'])
            task_concepts['total'] = all_concepts
            args.task_concepts[config] = task_concepts
        elif args.subtask == 'visual_bias':
            task_concepts = {'train': list(all_concepts), 'val': list(all_concepts),
                             'total': all_concepts}
            args.task_concepts[config] = task_concepts
        else:
            task_concepts = {'train': list(all_concepts), 'val': list(all_concepts),
                             'total': all_concepts}
            args.task_concepts[config] = task_concepts

        selected_ids = np.random.choice(list(visual_dataset.keys()), args.max_sizeDataset)
        print('building question dataset')
        conceptualQuestion_counter = {'synonym': 0, 'isinstance': 0, 'bin_isinstance': 0}
        for scene_id in tqdm(selected_ids):
            scene = visual_dataset[scene_id]['scene_plain']
            if 'objects' not in scene:
                continue
            split = scene['split'] if not args.no_validation else 'train'
            if split == 'test':
                continue
            for j in range(args.questionsPimage):
                if not args.conceptual or \
                        np.random.random() > args.conceptual_question_ratio:
                    if args.subtask == 'classification':
                        question = cls.empty_question(scene)
                    elif 'exist' in args.subtask or (args.subtask == 'visual_bias' and args.group == 'toy'):
                        question = cls.exist_question(scene, config)
                    elif 'filter' in args.subtask or (args.subtask == 'visual_bias' and args.group == 'clevr'):
                        question = cls.filter_question(scene, config)
                    elif 'query' in args.subtask:
                        question = cls.query_question(scene, config)
                    else:
                        raise Exception('not such task supported as %s' % args.subtask)
                else:
                    if 'synonym' in args.subtask:
                        question = cls.synonym_question(split, config, conceptualQuestion_counter)
                    elif 'isinstance' in args.subtask:
                        question = cls.isinstance_question(split, config, conceptualQuestion_counter)
                    elif args.subtask == 'visual_bias':
                        if split == 'train' and not args.no_aid:
                            question = cls.isinstance_question(split, config, conceptualQuestion_counter)
                        else:
                            question = None
                    else:
                        raise Exception('no such conceptual question type found: %s' % args.subtask)

                if question is not None:
                    question['image_id'] = scene_id
                    question['split'] = split
                    questions.update({str(len(questions)): question})
        return questions

    @classmethod
    def empty_question(cls, scene):
        # filter-exist questions

        question = {
            'question': 'Please classifiy objects in the image.',
            'semantic': [
                {'operation': '<NULL>', 'argument': '<NULL>',
                'dependencies': []},
            ],
            'answer': 'None',
            'type': 'classification',
        }

        return question

    @classmethod
    def exist_question(cls, scene, config):
        # filter-exist questions
        queried = random_one(info.vocabulary['total'],
                             lambda x: x in args.task_concepts[config]['total'])
        which, answer = cls.filter_objects(scene, queried)

        queried = cls.alternative(queried, config)

        question = {
            'question': 'Are there any %s objects in the image?' % queried,
            'semantic': [
                {'operation': 'select', 'argument': '{0} ({1})'.format(queried, ', '.join(which)),
                'dependencies': []},
                {'operation': 'exist', 'argument': '?',
                'dependencies': [0]}
            ],
            'answer': answer,
            'type': 'filter-exist',
        }

        return question

    @classmethod
    def filter_question(cls, scene, config):
        # filter-filter-exist questions
        cat_1, cat_2 = np.random.choice(list(info.vocabulary.records), 2, replace=False)
        queried_1 = random_one(info.vocabulary[cat_1],
                               lambda x: x in args.task_concepts[config]['total'])
        queried_2 = random_one(info.vocabulary[cat_2],
                               lambda x: x in args.task_concepts[config]['total'])
        if not set([queried_1, queried_2]).issubset(set(args.task_concepts[config]['total'])):
            return None
        which_1, answer_1 = cls.filter_objects(scene, queried_1)
        which_2, answer_2 = cls.filter_objects(scene, queried_2)
        which_2 = list(set(which_1).intersection(set(which_2)))
        if which_2 == []:
            which_2 = ['-']
        answer = 'yes' if which_2 != ['-'] else 'no'

        queried_1, queried_2 = cls.alternative((queried_1, queried_2), config)

        question = {
            'question': 'Are there any %s %s objects in the image?' % (queried_1, queried_2),
            'semantic': [
                {'operation': 'select', 'argument': '{0} ({1})'.format(queried_1, ', '.join(which_1)),
                 'dependencies': []},
                {'operation': 'filter', 'argument': '{0} ({1})'.format(queried_2, ', '.join(which_2)),
                 'dependencies': [0]},
                {'operation': 'exist', 'argument': '?',
                 'dependencies': [1]}
            ],
            'answer': answer,
            'type': 'filter-filter-exist',
        }
        return question

    @classmethod
    def query_question(cls, scene, config):
        split = scene['split']
        found = False
        obj_id = random_one(scene['objects'])
        obj = scene['objects'][obj_id]
        for i in range(10):
            cat_1, cat_2, cat_3, cat_4 = random_one(info.vocabulary.records, num=4, replace=False)
            attr_1, attr_2, attr_3 = obj[cat_1], obj[cat_2], obj[cat_3]
            which_1 = cls.filter_objects(scene, attr_1)[0]
            which_2 = cls.filter_objects(scene, attr_2)[0]
            which_2 = list(set(which_1).intersection(set(which_2)))
            which_3 = cls.filter_objects(scene, attr_3)[0]
            which_3 = list(set(which_2).intersection(set(which_3)))
            answer = obj[cat_4]
            if len(set(which_1).intersection(set(which_2)).intersection(set(which_3))) == 1 and \
                    (args.subtask != 'query_isinstance_rev' or answer in args.task_concepts[config][split]) and\
                    set([attr_1, attr_2, attr_3, answer]).issubset(set(args.task_concepts[config]['total'])):
                found = True
                break
            else:
                continue

        if not found:
            return None

        question = {
            'question': 'What is the %s of the %s, %s, %s objects in the image'
                % (cat_4, attr_1, attr_2, attr_3),
            'semantic': [
                {'operation': 'select',
                 'argument': '{0} ({1})'.format(attr_1, ', '.join(which_1)),
                 'dependencies': []},
                {'operation': 'filter',
                 'argument': '{0} ({1})'.format(attr_2, ', '.join(which_2)),
                 'dependencies': [0]},
                {'operation': 'filter',
                 'argument': '{0} ({1})'.format(attr_3, ', '.join(which_3)),
                 'dependencies': [1]},
                {'operation': 'query', 'argument': cat_4, 'dependencies': [2]}
            ],
            'answer': answer,
            'type': 'filter-filter-filter-query',
        }
        return question

    @classmethod
    def synonym_question(cls, split, config, counter):
        task_concepts = args.task_concepts[config][split]
        queried_1 = random_one(task_concepts)
        counter['synonym'] += 0.5 * (1 + 1/(len(task_concepts)-1))
        if len(task_concepts) == 1 or\
                counter['synonym'] >= 1:
            counter['synonym'] -= 1
            queried_2 = queried_1
            answer = 'yes'
        else:
            queried_2 = random_one(task_concepts)
            answer = 'yes' if queried_2 == queried_1 else 'no'

        queried_1, queried_2 = cls.alternative((queried_1, queried_2), config)

        question = {
            'question': 'Is {} a synonym of {} ?'.format(queried_2, queried_1),
            'semantic': [
                {'operation': 'select_concept', 'argument': format(queried_1),
                 'dependencies': []},
                {'operation': 'synonym', 'argument': format(queried_2),
                 'dependencies': [1]}
            ],
            'answer': answer,
            'type': 'synonym',
        }
        return question

    @classmethod
    def isinstance_question(cls, split, config, counter):
        if args.subtask == 'query_isinstance_rev':
            split = 'total'
        task_concepts = list(args.task_concepts[config][split])
        counter['isinstance'] += 1

        if split == 'train':
            queried_1_cat = list(info.vocabulary.records)[counter['isinstance'] % len(info.vocabulary.records)]
            queried_1 = random_one(set(task_concepts).intersection(
                set(info.vocabulary[queried_1_cat])))
        else:
            queried_1 = task_concepts[counter['isinstance'] % len(task_concepts)]
            queried_1_cat = info.vocabulary.belongs_to(queried_1)

        queried_1 = cls.alternative(queried_1, config)

        question = {
            'question': 'What is {} an instance of?'.format(queried_1),
            'semantic': [
                {'operation': 'select_concept', 'argument': format(queried_1),
                 'dependencies': []},
                {'operation': 'isinstance', 'argument': '<NULL>',
                 'dependencies': [1]}
            ],
            'answer': queried_1_cat,
            'type': 'isinstance',
        }
        return question

    @classmethod
    @property
    def image_ids(cls):
        return list(cls.sceneGraphs)

    @classmethod
    def filter_objects(cls, scene, queried):
        which = ['-']
        answer = 'no'
        for obj_id, obj in scene['objects'].items():
            for at in obj.values():
                if isinstance(at, str) and at == queried:
                    if '-' in which:
                        which.remove('-')
                    which.append(obj_id)
                    answer = 'yes'
        return which, answer

    @classmethod
    def alternative(cls, concepts, config):
        if isinstance(concepts, str):
            return random_one(args.task_concepts[config]['total'][concepts])
        elif isinstance(concepts, tuple):
            return tuple([cls.alternative(x, config) for x in concepts])
