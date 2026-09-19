import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class RepositoryStatus(str, enum.Enum):
    pending = "pending"
    cloning = "cloning"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    status = Column(Enum(RepositoryStatus), default=RepositoryStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    files = relationship("File", back_populates="repository", cascade="all, delete-orphan")
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    sha = Column(String, nullable=False)
    author_name = Column(String, nullable=True)
    author_email = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    committed_at = Column(DateTime, nullable=False)

    repository = relationship("Repository", back_populates="commits")


class CommitFileChange(Base):
    __tablename__ = "commit_file_changes"

    id = Column(Integer, primary_key=True, index=True)
    commit_id = Column(Integer, ForeignKey("commits.id"), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True, index=True)
    path = Column(String, nullable=False)
    previous_path = Column(String, nullable=True)
    change_type = Column(String, nullable=False)  # added, modified, deleted, renamed

    commit = relationship("Commit")
    file = relationship("File")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    path = Column(String, nullable=False, index=True)
    language = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    repository = relationship("Repository", back_populates="files")
    symbols = relationship("Symbol", back_populates="file", cascade="all, delete-orphan")
    outgoing_dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.source_file_id",
        back_populates="source_file",
        cascade="all, delete-orphan",
    )
    incoming_dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.target_file_id",
        back_populates="target_file",
    )

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    name = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False) # e.g. function, class, method
    signature = Column(Text, nullable=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)

    file = relationship("File", back_populates="symbols")


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    target_file_id = Column(Integer, ForeignKey("files.id"), nullable=True, index=True)
    imported_module = Column(String, nullable=False)

    source_file = relationship(
        "File", foreign_keys=[source_file_id], back_populates="outgoing_dependencies"
    )
    target_file = relationship(
        "File", foreign_keys=[target_file_id], back_populates="incoming_dependencies"
    )
