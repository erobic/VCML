from argparse import ArgumentParser
import torch
import os
import pprint

class Config:
    def __init__(self):
        args = self.parse_args()
        self.__dict__.update(vars(args))
        self.post_process()
        self._print()

    def parse_args(self):
        parser = ArgumentParser()
        self.dir_args = []
        def dir_add_argument(arg_name, **kwargs):
            self.dir_args.append(arg_name.strip('-'))
            parser.add_argument(arg_name, **kwargs)

        parser.add_argument('--data_dir', default='../data')
        dir_add_argument('--image_dir', default='raw/allImages/images')
        dir_add_argument('--sceneGraph_h5', default='processed/SG.h5')
        dir_add_argument('--sceneGraph_json', default='raw/sceneGraphs/all_sceneGraphs.json')
        dir_add_argument('--vocabulary_file', default='processed/vocabulary.json')
        dir_add_argument('--protocol_file', default='processed/protocol.json')
        parser.add_argument('--allow_output_protocol', action='store_true')
        dir_add_argument('--questions_h5', default='processed/questions')
        dir_add_argument('--questions_json', default='raw/questions/all_balanced_questions.json')

        parser.add_argument('--max_nImages', default=-1)
        parser.add_argument('--box_scale', default=1024)
        parser.add_argument('--image_scale', default=592)

        parser.add_argument('--num_workers', default=1)
        parser.add_argument('--train_shuffle', action='store_true')
        parser.add_argument('--mode', default='concept-net',
                            choices=['concept-net'])
        parser.add_argument('--batch_size', type=int, default=7, metavar='N',
                            help='input batch size for training (default: 64)')
        parser.add_argument('--epochs', type=int, default=20, metavar='N',
                            help='number of epochs to train (default: 10)')
        parser.add_argument('--lr', type=float, default=0.003, metavar='LR')
        parser.add_argument('--loss', type=str, default='mse',
                            choices=['mse', 'weighted', 'first', 'last'])
        parser.add_argument('--curriculum_learning', action='store_true')
        parser.add_argument('--perfect_th', type=float, default=0.05)

        parser.add_argument('--toy', action='store_true')
        parser.add_argument('--toy_objects', type=int, default=5)
        parser.add_argument('--toy_names', type=int, default=20)
        parser.add_argument('--toy_attributes', type=int, default=20)
        parser.add_argument('--toy_attributesPobject', type=int,
                            default=3)
        parser.add_argument('--size_toy', type=int, default=10000)
        parser.add_argument('--toy_mode', default='exist',
                            choices=['exist', 'exist&query'])

        parser.add_argument('--ckpt', type=str)
        parser.add_argument('--name', type=str)
        parser.add_argument('--game', type=str, default='locked',
                            choices=['rotate', 'locked', 'freely', 'oscillate'],)

        parser.add_argument('--max_program_length', type=int, default=10)
        parser.add_argument('--max_question_length', type=int, default=50)
        parser.add_argument('--max_relations', type=int, default=100)
        parser.add_argument('--max_concepts', type=int, default=3300)
        parser.add_argument('--max_objects', type=int, default=100)
        parser.add_argument('--num_classes', type=int, default=1800)
        parser.add_argument('--num_attributes', type=int, default=900)
        parser.add_argument('--size', type=int, default=4)
        parser.add_argument('--num_action', type=int, default=4)
        parser.add_argument('--size_dataset', type=int, default=5000)

        parser.add_argument('--relation_direction', default='directed',
                            choices=['directed', 'undirected'])
        parser.add_argument('--question_filter', default='None',
                            choices=['None', 'existance'])

        parser.add_argument('--embed_dim', type=int, default=100)
        parser.add_argument('--hidden_dim', type=int, default=100)
        parser.add_argument('--attention_dim', type=int, default=5)
        parser.add_argument('--operation_dim', type=int, default=3)
        parser.add_argument('--size_attention', type=int, default=30)

        return parser.parse_args()

    def post_process(self):
        self.num_gpus = torch.cuda.device_count()
        self.use_cuda = self.num_gpus > 0
        self.device = torch.device('cuda' if self.use_cuda else 'cpu')
        self.load_by = 'question' if self.mode in ['concept-net']\
            else 'image'
        for arg in self.dir_args:
            self.__dict__[arg] = os.path.join(self.data_dir,
                                              self.__dict__[arg])

    def _print(self):
        pprint.pprint('Arguments: ------------------------')
        pprint.pprint(self.__dict__)
        pprint.pprint('-----------------------------------')
